"""HC-15: authored Enforce bodies, SYNTHETIC native handles/clock/players.

No engine, herd, perception, pair-matrix or inventory acceptance evidence.
RED (2026-11-18), existing raw HCEcologyRuntime.Add called from two alias
origins for one handle: AssertionError: 1 != 2 : duplicate herd/territory
aliases created double ownership. Ran 1 test; FAILED (failures=1).
Command: PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=.:tests/unit python3 -m unittest test_hc_wildlife -v
The GREEN harness uses the new deduplicating port; existing EEInit guards and
the raw registry are unchanged. All policy below executes authored bodies.
Follow-up RED: the same test rejected a skinned carcass still in HCFacts;
GREEN: same focused command, Ran 1 test, OK after native IsSkinned recheck.
Required checks GREEN: PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=.:tests/unit python3
-m unittest test_hc_wildlife test_script_syntax test_enforce_locals
test_script_identifiers test_hygiene -v -> Ran 54 tests, OK.

HC-49 / #149 extends this SAME feature check and manifest validation.
Actual RED: AssertionError: HC-49 observed carcass receipt handler missing.
Follow-up RED: AssertionError: False is not true (missing named persistent-ID
refusal). Same focused command above GREEN: Ran 1 test ... OK.
GREEN required checks: PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=.:tests/unit python3
-m unittest test_hc_wildlife test_hc_wildlife_wiring test_v1_ecology_resources
test_script_syntax test_enforce_locals test_script_identifiers test_hygiene
test_enforce_formula_complexity -v -> Ran 66 tests, OK.
Synthetic journal/body/story ports establish no DayZ or paired-Hive durability.
"""
import functools
import copy
import json
from pathlib import Path
import re
from types import MethodType, SimpleNamespace as N
import unittest

from tests.unit.test_ecology_runtime import environment
from tests.unit.test_event_runtime import translate
from tests.unit.test_group_server import EArray, body
from tests.unit.test_hc_unit_budget import unit_budget

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / 'mods/HollowCountry/scripts/4_World/Ecology/HCWildlifeObservation.c'
CONFIG = ROOT / 'mission/hollow-country/ecology/species.json'


def carcass_fixture(image=None, enabled=True):
    """HC-49 extension of HC-15; all disk, story and native ports SYNTHETIC."""
    from tests.unit.test_map_layers import EStr, methods, translate as handlers
    path = SOURCE.parent / 'HCWildlifeScenes.c'
    if not path.is_file():
        raise AssertionError('HC-49 observed carcass receipt handler missing')
    text = path.read_text().replace('    protected ', '    ')
    text = re.sub(r'\bthis\b', 'self', text)
    text = text.replace('retained.ToString()', 'str(retained)')
    text = re.sub(r'array<[^>]+>(?= \w+ =)', 'HCArray', text)
    text = text.replace('new HCEncounterStore<HCWildlifeSceneState>("hc49-carcasses")',
                        'new SyntheticStore()')
    disk = N(image=copy.deepcopy(image), fail=False)
    logs, calls, snapshots = [], [], EArray()
    def save(state):
        calls.append('save')
        if disk.fail: return False
        disk.image = copy.deepcopy(state)
        return True
    config = N(**json.loads((CONFIG.parent / 'carcass-sites.json').read_text()))
    config.Sites = EArray(config.Sites)
    env = dict(str=str, GetGame=lambda: N(IsServer=lambda: True), Print=logs.append,
        HCEcologyNative=N(Authority=lambda: True),
        HCV2Admission=N(Admitted=lambda preference: preference),
        HCEventDirector=N(TextValid=lambda value, cap: bool(value) and len(value) <= cap),
        HCSearchSupplyRegistry=N(PersistentId=lambda handle: handle.pid),
        HCWildlifeObservation=N(HCSnapshot=lambda now: snapshots),
        HCStoryPolicy=N(HCValid=lambda state: True),
        HCEcologyRuntimeIO=N(Read=lambda *args: ''),
        HCWildlifeSceneState=lambda: N(Version=1, Rows=EArray()),
        HCWildlifeSceneRow=lambda: N(Id=EStr(''), StorySequence=0, CorpseId=EStr(''),
            Supply=EStr('pending'), Origin=EStr('observed'), DueAt=0, EndsAt=0),
        SyntheticStore=lambda: N(Load=lambda fresh, collection: calls.append('load') or
            copy.deepcopy(disk.image or fresh), Save=save),
        HCOperationalStatus=lambda: N(HCPublish=lambda *args: None),
        HCWildlifeSceneDebug=lambda: N(Owner=None),
        HCDebugSnapshot=N(HCRegister=lambda value: calls.append('debug_add'),
                          HCUnregister=lambda value: calls.append('debug_remove')))
    # Execute the authored survey's native read policy; PID is a synthetic port.
    survey_env = dict(env, AnimalBase=N(Cast=lambda value: value if isinstance(value, SyntheticAnimal) else None))
    handlers((SOURCE.parent/'HCEcologyResourceSurvey.c').read_text().replace('\t', '    '),
             'HCEcologyResourceSurvey', survey_env, only=('Carcass', 'CarcassSupply'))
    env['HCEcologyResourceSurvey'] = N(Carcass=survey_env['Carcass'], CarcassSupply=survey_env['CarcassSupply'])
    table, _ = methods(text, 'HCWildlifeScenes')
    handlers(text, 'HCWildlifeScenes', env, only=tuple(name for name in table if name != 'HCLoadConfig'))
    env['HCLoadConfig'] = lambda: config  # JSON decoding only, policies run below.
    owner = N(m_State=None, m_Store=None, m_Config=None, m_Active=None, m_Body=None,
        m_Enabled=False, m_Fault=False, m_Opened=False, m_Cursor=0, m_LastTick=-1,
        m_LastNow=-1, m_Effective=EStr('off'), m_Reason=EStr('not_started'), m_Reports=0,
        m_Debug=None, m_Units=unit_budget(),
        m_Work=N(HCReset=lambda *args: None, HCContinue=lambda: True))
    for name, (static, _, _) in table.items():
        setattr(owner, name, env[name] if static else MethodType(env[name], owner))
    owner.HCOpen(enabled)
    animal = SyntheticAnimal(object())
    animal.alive = False
    animal.pid = EStr('synthetic-native-corpse-1')
    snapshots.append(N(Subject=animal, Carcass=True))
    chain = N(Id=EStr('synthetic-story-1'), StorySequence=1, DueAt=100, ExpiresAt=200,
              Complete=False, Cancelled=False)
    state = N(Chains=EArray([chain]), Stories=N(LegacyThrough=0, NextSequence=2))
    return N(owner=owner, disk=disk, calls=calls, logs=logs, animal=animal,
             snapshots=snapshots, chain=chain, state=state, config=config)


def rename(text):
    return re.sub(r'\b(HCWildlife\w*|HCEcology\w*|HCV2Admission|DayZAnimalInputController|AnimalBase|AIAgent|Man)\b',
                  lambda m: 'HCEvent' + m[0], text)


def authored(text, method, env, owner, member=False):
    text = re.sub(r'new array<([^>]+)>(?!\s*\()', r'new array<\1>()', rename(text))
    return translate(text, method, {rename(k): v for k, v in env.items()}, rename(owner), member)


class SyntheticAnimal:
    """Identity equality matches native handles; no gameplay decisions here."""
    def __init__(self, group):
        self.position = [10., 0., 10.]
        self.alive = True
        self.deleted = self.skinned = False
        self.group = group
    def IsPendingDeletion(self): return self.deleted
    def IsAlive(self): return self.alive
    def IsSkinned(self): return self.skinned
    def CanBeSkinned(self): return True
    def GetPosition(self): return self.position
    def GetType(self): return 'Animal_CervusElaphus_Synthetic'
    def IsKindOf(self, species): return species == 'Animal_CervusElaphus'
    def GetInputController(self): return N(GetBehaviourSlot=lambda: 12, GetBehaviourAction=lambda: 7)
    def GetAIAgent(self): return N(GetGroup=lambda: self.group)


class WildlifeBehavior(unittest.TestCase):
    def harness(self):
        self.assertTrue(SOURCE.is_file(), 'missing HC-15 authored port')
        text = SOURCE.read_text()
        owner_text = body(text, re.search(r'class HCWildlifeObservation\s*\{', text).end())
        env = environment()
        limits = (SOURCE.parents[2] / '3_Game/Ecology/HCEcologyData.c').read_text()
        env['HCEcologyLimits'].TEXT = int(re.search(r'TEXT = (\d+)', limits)[1])
        rules = (SOURCE.parent / 'HCEcologyRules.c').read_text()
        env['HCEcologyRules'] = N(TextValid=authored(rules, 'TextValid', env, 'HCEcologyRules'))
        env['EArray'] = EArray
        env['AnimalBase'] = N(Cast=lambda obj: obj if isinstance(obj, SyntheticAnimal) else None)
        self.authority = True
        self.logs, self.contributors = [], []
        self.players = EArray([N(IsAlive=lambda: True, GetPosition=lambda: [0., 0., 0.])])
        env['HCEcologyNative'] = N(Authority=lambda: self.authority)
        env['HCPerfPlayers'] = N(HCGet=lambda: self.players)
        env['HCDebugSnapshot'] = N(HCRegister=self.contributors.append, HCUnregister=self.contributors.remove)
        env['Print'] = self.logs.append
        admission = (SOURCE.parents[0].parent / 'Core/HCV2Admission.c').read_text()
        env['HCV2Admission'] = N()
        for method in ('Admitted', 'Line', 'OnOff'):
            setattr(env['HCV2Admission'], method, authored(admission, method, env, 'HCV2Admission'))
        # DTO scaffolding reads authored fields/defaults; no policy surrogate.
        for kind in ('HCWildlifeFact', 'HCWildlifeBinding'):
            fields = body(text, re.search(r'class ' + kind + r'\s*\{', text).end())
            declarations = re.findall(r'^\s*(?:ref )?(\w+) (\w+)(?: = ([^;]+))?;', fields, re.M)
            def factory(declarations=declarations):
                return N(**{key: json.loads(value) if value else {'string':'', 'bool':False,
                    'int':0, 'vector':[0.,0.,0.]}.get(typ) for typ,key,value in declarations})
            env[kind] = factory
        env['HCWildlifeDebugContributor'] = lambda: N(Owner=None)
        state = N(state='unknown', reason='unknown')
        state.HCPublish = lambda s, r: (setattr(state, 'state', s), setattr(state, 'reason', r))
        owner = N(m_Bindings=EArray(), m_Config=None, m_Units=unit_budget(),
                  m_Work=N(HCReset=lambda *args: None, HCContinue=lambda: True),
                  m_Status=state, m_Debug=None, m_Collecting=True, m_Running=False,
                  m_OverflowReported=False, m_NextSerial=1, m_Cursor=0,
                  m_LastTick=-1, m_LastNow=-1)
        policy = N()
        env['HCWildlifeObservation'] = policy
        for method in ('HCConfigValid', 'HCDestinationSupported', 'HCFeedingSupported', 'HCTargetObservationSupported'):
            setattr(policy, method, authored(owner_text, method, env, 'HCWildlifeObservation'))
            setattr(owner, method, getattr(policy, method))
        for method in ('HCBegin', 'HCAdd', 'HCRemove', 'HCNear', 'HCRead', 'HCSample', 'HCFacts', 'HCEnd', 'HCRefuse'):
            setattr(owner, method, functools.partial(authored(owner_text, method, env, 'HCWildlifeObservation', True), owner))
        config = json.loads(CONFIG.read_text())
        config['Species'] = EArray(config['Species'])
        config['TargetPairs'] = EArray(N(**p) for p in config['TargetPairs'])
        return owner, N(**config)

    def test_aliases_share_one_native_owner_and_unsupported_commands_refuse(self):
        owner, config = self.harness()
        animal = SyntheticAnimal(object())
        for alias in ('synthetic-herd', 'synthetic-territory'):
            self.assertTrue(owner.HCAdd(animal), alias)
        self.assertEqual(1, owner.m_Bindings.Count(),
                         'duplicate herd/territory aliases created double ownership')
        self.assertTrue(owner.HCBegin(True, config))
        owner.HCSample(100)
        facts = owner.HCFacts(100)
        self.assertEqual(1, facts.Count())
        self.assertIs(animal.group, facts[0].NativeGroup)
        self.assertEqual((12, 7), (facts[0].BehaviourSlot, facts[0].BehaviourAction))
        self.assertFalse(facts[0].TargetKnown)  # HUNTING still does not identify prey.
        self.assertIsNone(facts[0].Target)
        facts[0].Species = 'mutated-consumer-copy'
        self.assertEqual(animal.GetType(), owner.HCFacts(100)[0].Species)
        for method in ('HCDestinationSupported', 'HCFeedingSupported', 'HCTargetObservationSupported'):
            self.assertFalse(getattr(owner, method)())
        for capability in ('destination', 'feeding', 'animal_target'):
            self.assertTrue(any('capability=' + capability in line and 'state=refused' in line for line in self.logs))
        self.assertTrue(any('targets=5 state=ready' in line and 'observed_targets=0 runtime=PENDING' in line for line in self.logs))

        # Finite carcass evidence is revoked on native skinning/deletion/death,
        # and clock/freshness checks never replay an observation into a new life.
        animal.alive = False
        self.assertEqual([], owner.HCFacts(100))
        owner.HCSample(1100)
        self.assertTrue(owner.HCFacts(1100)[0].Carcass)
        animal.skinned = True
        self.assertEqual([], owner.HCFacts(1100))
        animal.skinned = False
        animal.deleted = True
        self.assertEqual([], owner.HCFacts(1100))
        animal.deleted = False
        self.assertEqual([], owner.HCFacts(1100 + config.FactLifetimeMs + 1))

        # Work-unit/time yields retain the next animal; configured range is
        # observation-only. Off/stop releases the debug contributor and handles.
        other = SyntheticAnimal(object())
        self.assertTrue(owner.HCAdd(other))
        config.WorkUnits = 1
        owner.m_Cursor = 0
        owner.HCSample(2100)
        self.assertEqual(1, owner.m_Cursor)
        owner.m_Work.HCContinue = lambda: False
        owner.HCSample(3100)
        self.assertEqual(1, owner.m_Cursor)
        owner.m_Work.HCContinue = lambda: True
        owner.HCSample(4100)
        self.assertEqual(2, owner.m_Cursor)
        config.MaxFacts = 1
        self.assertEqual(1, len(owner.HCFacts(4100)))
        self.players[0].GetPosition = lambda: [config.PlayerObservationRadiusM * 2, 0., 0.]
        owner.HCSample(5100)
        owner.HCSample(6100)
        self.assertEqual([], owner.HCFacts(6100))
        owner.HCRemove(animal)
        self.assertEqual([other], [row.Live for row in owner.m_Bindings])
        owner.HCEnd()
        self.assertEqual([], self.contributors)
        self.assertEqual([], owner.m_Bindings)
        self.assertFalse(owner.HCAdd(other))
        self.assertFalse(owner.HCBegin(False, None))
        owner.HCSample(7100)
        self.assertEqual([], owner.HCFacts(7100))
        self.assertEqual('off', owner.m_Status.state)
        self.assertTrue(owner.HCBegin(True, config))
        self.assertTrue(owner.HCAdd(other))
        owner.HCSample(8100)
        owner.HCSample(8000)  # rollback refuses and clears the entire port
        self.assertEqual('refused', owner.m_Status.state)
        self.assertEqual([], owner.HCFacts(8100))
        self.assertEqual([], self.contributors)

        for field, invalid in (('PlayerObservationRadiusM', float('nan')), ('MaxAnimals', 257)):
            old = getattr(config, field)
            setattr(config, field, invalid)
            self.assertFalse(owner.HCBegin(True, config), field)
            setattr(config, field, old)
        config.TargetPairs[0].Verdict = 'accepted_from_config'
        self.assertFalse(owner.HCBegin(True, config))

        # HC-49 reuses this feature check: no second test/model/controller.
        scene = carcass_fixture()
        self.assertTrue(scene.owner.HCOffer(scene.chain, scene.state))
        scene.owner.HCStep(100, 1000)
        self.assertEqual('native_skinnable', scene.disk.image.Rows[0].Supply)
        self.assertEqual(scene.animal.pid, scene.disk.image.Rows[0].CorpseId)
        self.assertFalse(scene.owner.HCOffer(scene.chain, scene.state))
        scene.animal.skinned = True
        scene.animal.deleted = True  # skinning marks spent before native deletion
        scene.owner.HCStep(101, 2000)
        self.assertEqual('depleted', scene.disk.image.Rows[0].Supply)
        scene.animal.skinned = scene.animal.deleted = False
        self.assertFalse(scene.owner.HCOffer(scene.chain, scene.state))
        restarted = carcass_fixture(scene.disk.image)
        self.assertFalse(restarted.owner.HCOffer(restarted.chain, restarted.state))
        # A different story cannot claim the same persisted native body either.
        restarted.chain.Id = 'synthetic-story-2'
        restarted.chain.StorySequence = 2
        restarted.state.Stories.NextSequence = 3
        self.assertTrue(restarted.owner.HCOffer(restarted.chain, restarted.state))
        restarted.owner.HCStep(100, 1000)
        self.assertEqual('pending', restarted.disk.image.Rows[-1].Supply)
        self.assertIsNone(restarted.owner.m_Body)

        active = carcass_fixture()
        active.owner.HCOffer(active.chain, active.state)
        active.owner.HCStep(100, 1000)
        crashed = carcass_fixture(active.disk.image)
        self.assertEqual('unknown', crashed.disk.image.Rows[0].Supply)
        self.assertIsNone(crashed.owner.m_Body)
        self.assertFalse(crashed.owner.HCOffer(crashed.chain, crashed.state))
        active.animal.deleted = True
        active.owner.HCStep(101, 2000)
        self.assertEqual('unavailable', active.disk.image.Rows[0].Supply)

        failed = carcass_fixture()
        failed.owner.HCOffer(failed.chain, failed.state)
        failed.disk.fail = True
        failed.owner.HCStep(100, 1000)
        self.assertTrue(failed.owner.m_Fault)
        self.assertIsNone(failed.owner.m_Body, 'failed barrier cannot expose native body')
        calls = len(failed.calls)
        failed.owner.HCStep(101, 2000)
        self.assertEqual(calls, len(failed.calls))
        bad = carcass_fixture(N(Version=0, Rows=EArray()))
        self.assertTrue(bad.owner.m_Fault, 'missing native JSON version must refuse')
        self.assertNotIn('save', bad.calls)
        off = carcass_fixture(enabled=False)
        off.owner.HCStep(100, 1000)
        self.assertEqual([], off.calls, 'off does no scan, save or debug registration')
        stopped = carcass_fixture()
        stopped.owner.HCOffer(stopped.chain, stopped.state)
        stopped.owner.HCClose()
        calls = len(stopped.calls)
        stopped.owner.HCStep(100, 1000)
        stopped.owner.HCClose()
        self.assertEqual(calls, len(stopped.calls))
        self.assertEqual('unknown', stopped.disk.image.Rows[0].Supply)

        unknown = carcass_fixture()
        unknown.animal.pid = ''
        unknown.owner.HCOffer(unknown.chain, unknown.state)
        unknown.owner.HCStep(100, 1000)
        self.assertIsNone(unknown.owner.m_Body)
        self.assertTrue(any('CARCASS_PERSISTENT_ID_UNAVAILABLE' in line for line in unknown.logs))
        sliced = carcass_fixture()
        sliced.config.SamplesPerTick = sliced.config.WorkUnits = 1
        living = SyntheticAnimal(object())
        sliced.snapshots.insert(0, N(Subject=living, Carcass=True))
        sliced.owner.HCOffer(sliced.chain, sliced.state)
        sliced.owner.HCStep(100, 1000)
        self.assertEqual(1, sliced.owner.m_Cursor)
        self.assertIsNone(sliced.owner.m_Body, 'alive animal is not a carcass')
        sliced.owner.m_Work.HCContinue = lambda: False
        sliced.owner.HCStep(101, 2000)
        self.assertEqual(1, sliced.owner.m_Cursor, 'time yield retains next fact')
        sliced.owner.m_Work.HCContinue = lambda: True
        sliced.owner.HCStep(102, 3000)
        self.assertEqual('native_skinnable', sliced.disk.image.Rows[0].Supply)
        full_image = copy.deepcopy(scene.disk.image)
        full_image.Rows = EArray(copy.deepcopy(full_image.Rows[0]) for _ in range(64))
        for index, row in enumerate(full_image.Rows):
            row.Id, row.StorySequence, row.CorpseId = 'old-' + str(index), index + 1, 'body-' + str(index)
        full = carcass_fixture(full_image)
        self.assertFalse(full.owner.HCOffer(full.chain, full.state))
        self.assertEqual(64, len(full.owner.m_State.Rows), 'history never evicts depleted receipts')
        self.assertNotIn('save', full.calls)
        expired = carcass_fixture()
        expired.owner.HCOffer(expired.chain, expired.state)
        expired.owner.HCStep(200, 1000)
        self.assertEqual('missed', expired.disk.image.Rows[0].Supply)

        self.assertTrue(any('AUTHORED_CORPSE_CE_ADMISSION_UNPROVEN' in line for line in scene.logs))
        self.assertTrue(any('HC-49 carcass=synthetic-story-1-carcass origin=observed supply=native_skinnable'
                            in line and 'runtime=PENDING' in line for line in scene.logs))
        # Manifest validation runs authored policy; no new distances or authored loot.
        self.assertEqual([], scene.config.Sites)
        self.assertTrue(scene.owner.HCConfigValid(scene.config))
        scene.config.Version = 0
        self.assertFalse(scene.owner.HCConfigValid(scene.config))
        config.TargetPairs[0].Verdict = 'pending_native_pair_matrix'
        self.authority = False
        self.assertFalse(owner.HCAdd(other))
        self.assertFalse(owner.HCBegin(True, config))


if __name__ == '__main__':
    unittest.main()
