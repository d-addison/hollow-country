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

Wave 6 wiring / HC-49, actual RED (2026-11-18): same focused command above,
Ran 1 test; FAILED (failures=4). Pending close: 'pending' != 'unknown';
invalid UTC: disk pending != unknown; full terminal history: False is not true;
runtime contract: 'protected ref HCWildlifeScenes m_WildlifeScenes;' not found.
GREEN: same focused command, Ran 1 test; OK. Executed authored owner lifecycle,
story save/sequence gate, receipt eviction, restart and cached-status policies
through explicitly synthetic collaborators, with no native qualification.
GREEN required command:
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=.:tests/unit python3 -m unittest test_hc_wildlife test_hc_wildlife_wiring test_v1_ecology_resources test_script_syntax test_enforce_locals test_script_identifiers test_hygiene test_enforce_formula_complexity -v
Ran 66 tests; OK.
Affected-file regression command:
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=.:tests/unit python3 -m unittest test_hc_wildlife test_hc_wildlife_wiring test_ecology_module test_hc_story_module test_hc_story_schedule test_hc_unit_budget test_v2_scenes test_v2_leads test_v1_combined_flags test_v1_ecology_sight test_script_syntax test_enforce_locals test_script_identifiers test_hygiene test_enforce_formula_complexity -v
Ran 181 tests; FAILED (failures=7, errors=8, expected failures=1).
The two out-of-scope legacy fixtures need static owner/status/carcass ports
(test_ecology_module) and the new type spelling/Stories DTO
(test_hc_story_module). Combined flags imports the ecology fixture.
Those files remain untouched; lead integration must update their scaffolding.
Validating those two proposed fixture edits in memory only (no file writes),
the ecology/story/combined-flags subset ran 52 tests; OK (expected failures=1).

Wave 7 / #181, HC-49 follow-ups (2026-11-19).
Trace: supplied Wave-7 task -> cheap HCActive before UTC, independent ecology
and HC-49 cached statuses, durable bounded spent IDs, named Stories-off refusal.
Same pre-edit RED command recorded in test_hc_visual_seasons.py: Ran 7 tests;
FAILED (failures=11). Wildlife failures included these actual output lines:
  AssertionError: 'pending' != 'native_skinnable' : evicted scene corpse was offered again
  AssertionError: False is not true : Stories-off scene has no named refusal seam
  AssertionError: 2 != 1 : legacy journal never migrated
  Status assertion: HC-49 replaced ecology operational status.
  Inactive tick events incorrectly gained ('utc',), ('step', 100, 4321).
GREEN: the exact required 102-test command and 141-test reader/guard command
are recorded in test_hc_visual_seasons.py; both passed, with one pre-existing
expected failure in the required command. Fixtures changed in
 test_ecology_module.py only supply the new HCActive/independent status ports.
No production engine/provider/clock/IO behavior is implemented in the fixtures.
Framework: HCModule lifecycle/status, HCUnitBudget + HCWorkBudget + retained
cursor, HCPerfPlayers-backed HC-15 snapshots, HCV2Admission, bounded debug
contributor and HCEncounterStore synchronous transition barriers. No new
scheduler, distances or mission/ files. Registration blocks unchanged.
Native rechecked: EnScript.c:394 Find, :407 Insert, :470 RemoveOrdered;
Game.c:1535 GetTime. Source provenance is the pinned scripts-1.30.164289 tree.
The independent spent-ID ring retains up to 64 IDs and never overwrites one;
CARCASS_SPENT_HISTORY_FULL refuses new bindings at saturation. Version 1
migrates retained IDs once behind a barrier; Version 0 and invalid Version 2
refuse. Pre-fix evicted IDs are unrecoverable; migration cannot prove their
absence. Future ring eviction would require native corpse-lifetime evidence.
Chosen disposition is refusal, not story replay: HCStoryOff(sceneId) logs
STORIES_NOT_READY once per retained scene identity (64 plus one overflow line,
process-local). Actual owner is HCScenesModule.m_Stories / HCStorySchedule,
not a class named Stories module. Owed lead edit, outside worker file scope:
in HCScenesModule.c Work(), inside !lease.StoryPublished, immediately after
PublishSceneStory(chain, HCSceneChains.Site(plan.SiteId)), insert:
    if (chain.Stage == 0 && (!m_Stories || !m_Stories.HCReady()))
    {
        HCWildlifeScenes.HCStoryOff(chain.Id);
    }
This call site remains unwired by this worker; helper testing is not a claim
that the live scene publisher emits it. HCGetWildlifeStatus() exposes HC-49's
separate cached status; HCGetOperationalStatus() remains Ecology's own status.
No HCModule.c/config.cpp/MISSION_FILES edits required. HC-11 central trace
reconciliation remains with the lead (requested spec/plan/task files absent).
Grep HC-49, CARCASS_SPENT_HISTORY_FULL, STORIES_NOT_READY and existing
AUTHORED_CORPSE_CE_ADMISSION_UNPROVEN after exact-source DayZDiag, then normal
PBO/server. Observe no corpse re-offer after eviction/restart, off no-op,
native skinning, one refusal on Stories-off first-stage publication, independent
Ecology/HC-49 status and bounded diagnostic counts. Two-client visibility and
inventory, paired Hive/journal restoration and exact package hashes PENDING.
Nothing observed in DayZ yet.
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
    text = text.replace('receiptCap.ToString()', 'str(receiptCap)')
    text = re.sub(r'array<[^>]+>(?= \w+ =)', 'HCArray', text)
    text = text.replace('new HCEncounterStore<HCWildlifeSceneState>("hc49-carcasses")',
                        'new SyntheticStore()')
    disk = N(image=copy.deepcopy(image), fail=False)
    logs, calls, snapshots = [], [], EArray()
    if disk.image is not None and not hasattr(disk.image, 'SpentCorpseIds'):
        disk.image.SpentCorpseIds = None  # Explicit synthetic legacy JSON field absence.
    def save(state):
        calls.append('save')
        if disk.fail: return False
        disk.image = copy.deepcopy(state)
        return True
    config = N(**json.loads((CONFIG.parent / 'carcass-sites.json').read_text()))
    config.Sites = EArray(config.Sites)
    status = N(state='unknown', reason='unknown')
    status.HCPublish = lambda state, reason: (setattr(status, 'state', state), setattr(status, 'reason', reason))
    cap = int(re.search(r'MAX_RECEIPTS = (\d+);', text)[1])
    env = dict(str=str, GetGame=lambda: N(IsServer=lambda: True), Print=logs.append,
        HCWildlifeScenes=N(MAX_RECEIPTS=cap, MAX_SPENT_CORPSES=int(re.search(r'MAX_SPENT_CORPSES = (\d+);', text)[1])), s_StoryOff=EArray(),
        HCEcologyNative=N(Authority=lambda: True),
        HCV2Admission=N(Admitted=lambda preference: preference),
        HCEventDirector=N(TextValid=lambda value, cap: bool(value) and len(value) <= cap),
        HCSearchSupplyRegistry=N(PersistentId=lambda handle: handle.pid),
        HCWildlifeObservation=N(HCSnapshot=lambda now: snapshots),
        HCStoryPolicy=N(HCValid=lambda state: True),
        HCEcologyRuntimeIO=N(Read=lambda *args: ''),
        HCWildlifeSceneState=lambda: N(Version=int(re.search(r'int Version = (\d+);', text)[1]),
                                      Rows=EArray(), SpentCorpseIds=EArray()),
        HCWildlifeSceneRow=lambda: N(Id=EStr(''), StorySequence=0, CorpseId=EStr(''),
            Supply=EStr('pending'), Origin=EStr('observed'), DueAt=0, EndsAt=0),
        SyntheticStore=lambda: N(Load=lambda fresh, collection: calls.append('load') or
            copy.deepcopy(disk.image or fresh), Save=save),
        HCOperationalStatus=lambda: status,
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
        m_Debug=None, m_Status=status, m_Units=unit_budget(),
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


def check_carcass_runtime(test):
    """Execute the two owned module seams; all collaborators are SYNTHETIC.

    The existing restricted translator supplies syntax only. Static storage is
    an explicit namespace because Python function assignment is not Enforce
    class-static assignment. No engine/runtime acceptance is asserted.
    """
    from tests.unit.test_ecology_module import EcologyModuleBehavior
    from tests.unit.test_map_layers import translate as handlers
    legacy = EcologyModuleBehavior()
    legacy.setUp()
    events, static_owner = [], N(instance=None)
    status = N(HCPublish=lambda *args: None)
    ecology_status = N(HCPublish=lambda *args: None)
    active = [True]
    carcasses = N(HCActive=lambda: active[0], HCOpen=lambda enabled: events.append(('open', enabled)),
                  HCStep=lambda now, now_ms: events.append(('step', now, now_ms)),
                  HCClose=lambda: events.append(('close',)), HCStatus=lambda: status)
    utc = [1577836900]
    env = dict(legacy.e, static_owner=static_owner, HCWildlifeScenes=lambda: carcasses,
               HCGroupClock=N(Utc=lambda: events.append(('utc',)) or utc[0]))
    source = legacy.source.replace('override ', '').replace('s_Instance', 'static_owner.instance')
    source = re.sub(r'\bthis\b', 'self', source)
    names = ('IsEnabled', 'OnStart', 'OnTick', 'OnStop', 'HCGetOperationalStatus', 'HCGetWildlifeStatus', 'HCWildlife')
    handlers(source, 'HCEcologyRuntimeModule', env, only=names)
    owner = legacy.module
    owner.m_WildlifeScenes, owner.m_Status = None, ecology_status
    owner.m_WildlifeStatus = status
    for name in names:
        setattr(owner, name, env[name] if name == 'HCWildlife' else MethodType(env[name], owner))
    test.assertIsNone(owner.HCWildlife())
    test.assertTrue(owner.IsEnabled(None))
    owner.OnStart(None)
    test.assertEqual([('open', True)], events)
    test.assertIs(carcasses, owner.HCWildlife())
    with test.subTest(wave7='separate ecology and HC-49 status'):
        test.assertIs(ecology_status, owner.HCGetOperationalStatus(), 'HC-49 replaced ecology operational status')
        test.assertIs(status, owner.HCGetWildlifeStatus())
    owner.OnStart(None)
    test.assertEqual([('open', True)], events, 'duplicate start never opens a second owner')
    owner.OnTick(1)
    test.assertEqual(('step', 100, 4321), events[-1])
    with test.subTest(wave7='inactive HC-49 skips UTC'):
        active[0] = False
        before = list(events)
        owner.OnTick(1)
        test.assertEqual(before, events, 'inactive carcass scenes read UTC')
        active[0] = True
    for invalid in (-1, 0, 1577836800):
        utc[0] = invalid
        before = list(events)
        owner.OnTick(1)
        test.assertEqual(before + [('utc',)], events, 'invalid group UTC skips carcass step')
    owner.OnStop()
    test.assertIsNone(owner.HCWildlife())
    test.assertIsNone(owner.m_WildlifeScenes)
    owner.OnStop()
    owner.OnTick(1)
    test.assertEqual(1, events.count(('close',)))
    legacy.settings.Enabled = False
    test.assertFalse(owner.IsEnabled(None))
    test.assertIsNone(owner.HCWildlife())

    # A successful save alone can be a retirement. Only an actual new arrival
    # offers its exact chain, after the story barrier, and never retries later.
    source = (SOURCE.parent.parent / 'Scenes/HCScenesModule.c').read_text()
    source = re.sub(r'array<[^>]+>(?= \w+ =)', 'HCArray', source)
    for saved, advanced, present in ((True, True, True), (True, False, True),
                                      (False, True, True), (True, True, False)):
        with test.subTest(saved=saved, advanced=advanced, ecology=present):
            calls = []
            arrived = N(StorySequence=9)
            state = N(Stories=N(NextSequence=9), Chains=EArray([N(StorySequence=8), arrived]))
            wildlife = N(HCOffer=lambda chain, current: calls.append(('offer', chain, current)))
            def step(now, released):
                calls.append('story-save')
                if advanced: state.Stories.NextSequence += 1
                return saved
            scene = N(m_Running=True, m_State=state,
                      m_Stories=N(HCReady=lambda: True, HCCandidate=lambda: None, HCStep=step),
                      SaveBarrierDone=lambda: calls.append('barrier'))
            env = dict(HCEcologyRuntimeModule=N(HCWildlife=lambda: wildlife if present else None),
                       HCEventModule=N(HCStoryArrived=lambda chain: calls.append(('story', chain))))
            handlers(source, 'HCScenesModule', env, only=('StoryStep',))
            env['StoryStep'](scene, 100)
            expected = ['story-save']
            if saved: expected.append('barrier')
            if saved and advanced: expected.append(('story', arrived))
            if saved and advanced and present: expected.append(('offer', arrived, state))
            test.assertEqual(expected, calls)


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
        active.owner.HCClose()
        self.assertEqual('unknown', active.disk.image.Rows[0].Supply)
        self.assertIsNone(active.owner.m_Body)
        # Separate deletion observation still runs through the same authored port.
        active = carcass_fixture()
        active.owner.HCOffer(active.chain, active.state)
        active.owner.HCStep(100, 1000)
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
        with self.subTest(hc49='pending survives stop and restart'):
            self.assertEqual('pending', stopped.disk.image.Rows[0].Supply)
            resumed = carcass_fixture(stopped.disk.image)
            self.assertIsNotNone(resumed.owner.m_Active)
            resumed.owner.HCStep(100, 1000)
            self.assertEqual('native_skinnable', resumed.disk.image.Rows[0].Supply)

        with self.subTest(hc49='invalid UTC does not burn the opportunity'):
            waiting = carcass_fixture()
            waiting.owner.HCOffer(waiting.chain, waiting.state)
            before = copy.deepcopy(waiting.disk.image)
            calls = list(waiting.calls)
            waiting.owner.HCStep(0, 1000)
            waiting.owner.HCStep(-1, 2000)
            self.assertEqual(before, waiting.disk.image)
            self.assertEqual(calls, waiting.calls)
            self.assertEqual((-1, -1), (waiting.owner.m_LastNow, waiting.owner.m_LastTick))
            waiting.owner.HCStep(100, 3000)
            self.assertEqual('native_skinnable', waiting.disk.image.Rows[0].Supply)

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
        full_image.Version = 1
        full_image.SpentCorpseIds = None  # SYNTHETIC pre-ledger legacy journal.
        full_image.Rows = EArray(copy.deepcopy(full_image.Rows[0]) for _ in range(64))
        for index, row in enumerate(full_image.Rows):
            row.Id, row.StorySequence, row.CorpseId = 'old-' + str(index), index + 1, 'body-' + str(index)
        full = carcass_fixture(full_image)
        self.assertEqual(1, full.calls.count('save'), 'legacy spent IDs require one migration barrier')
        full.calls.clear()
        self.assertFalse(full.owner.HCOffer(full.chain, full.state))
        self.assertEqual(64, len(full.owner.m_State.Rows), 'duplicate offer cannot evict a receipt')
        self.assertNotIn('save', full.calls)
        with self.subTest(hc49='oldest terminal receipt is evicted at the cap'):
            # SYNTHETIC shuffled history: sequence records issue order, not position.
            full_image.Rows[0], full_image.Rows[17] = full_image.Rows[17], full_image.Rows[0]
            capped = carcass_fixture(full_image)
            capped.chain.Id, capped.chain.StorySequence = 'synthetic-story-65', 65
            capped.state.Stories.NextSequence = 66
            self.assertTrue(capped.owner.HCOffer(capped.chain, capped.state))
            self.assertEqual(64, len(capped.disk.image.Rows))
            self.assertNotIn(1, [row.StorySequence for row in capped.disk.image.Rows])
            self.assertEqual('pending', capped.disk.image.Rows[-1].Supply)
            with self.subTest(wave7='spent body survives scene eviction and restart'):
                # Oldest scene was evicted; its native corpse remains spent.
                capped.animal.pid = 'body-0'
                capped.owner.HCStep(100, 1000)
                self.assertEqual('pending', capped.disk.image.Rows[-1].Supply,
                                 'evicted scene corpse was offered again')
                restored = carcass_fixture(capped.disk.image)
                restored.animal.pid = 'body-0'
                restored.owner.HCStep(100, 1000)
                self.assertIsNone(restored.owner.m_Body)
                self.assertEqual(64, len(restored.disk.image.SpentCorpseIds))
                restored.animal.pid = 'previously-unseen-body'
                restored.owner.HCStep(101, 2000)
                self.assertIsNone(restored.owner.m_Body)
                self.assertTrue(any('CARCASS_SPENT_HISTORY_FULL' in line for line in restored.logs))
                self.assertEqual(64, len(restored.disk.image.SpentCorpseIds))
            receipt = copy.deepcopy(capped.disk.image.Rows[-1])
            capped.chain.Id, capped.chain.StorySequence = 'synthetic-story-66', 66
            capped.state.Stories.NextSequence = 67
            self.assertFalse(capped.owner.HCOffer(capped.chain, capped.state))
            self.assertEqual(receipt, capped.disk.image.Rows[-1], 'pending is never evicted')
        with self.subTest(wave7='Stories-off refusal once'):
            refused = carcass_fixture()
            self.assertTrue(hasattr(refused.owner, 'HCStoryOff'), 'Stories-off scene has no named refusal seam')
            refused.owner.HCStoryOff('synthetic-stories-off-scene')
            refused.owner.HCStoryOff('synthetic-stories-off-scene')
            self.assertEqual(1, sum('STORIES_NOT_READY' in line for line in refused.logs))
            for serial in range(70):
                refused.owner.HCStoryOff('synthetic-off-' + str(serial))
            self.assertEqual(65, sum('STORIES_NOT_READY' in line for line in refused.logs))
            self.assertEqual(1, sum('scene=overflow' in line for line in refused.logs))
            self.assertEqual([], refused.disk.image.Rows if refused.disk.image else [])
        with self.subTest(wave7='spent ledger migration and safe saturation'):
            saturated = carcass_fixture(full_image)
            self.assertEqual(2, saturated.owner.m_State.Version, 'legacy journal never migrated')
            self.assertEqual(64, len(saturated.disk.image.SpentCorpseIds))
            saturated.chain.Id, saturated.chain.StorySequence = 'synthetic-story-65', 65
            saturated.state.Stories.NextSequence = 66
            self.assertTrue(saturated.owner.HCOffer(saturated.chain, saturated.state))
            saturated.owner.HCStep(100, 1000)
            self.assertIsNone(saturated.owner.m_Body, 'full spent ledger must fail closed')
            self.assertTrue(any('CARCASS_SPENT_HISTORY_FULL' in line for line in saturated.logs))
        with self.subTest(wave7='corrupt spent ledger refuses without repair'):
            for spent_ids in (None, EArray(['duplicate', 'duplicate']), EArray([''])):
                corrupt = N(Version=2, Rows=EArray(), SpentCorpseIds=spent_ids)
                denied = carcass_fixture(corrupt)
                self.assertTrue(denied.owner.m_Fault)
                self.assertNotIn('save', denied.calls)
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

        with self.subTest(hc49='cached status follows transitions beyond log cap'):
            cached = carcass_fixture()
            status = cached.owner.HCStatus()
            self.assertIs(status, cached.owner.HCStatus())
            self.assertEqual('ready', status.state)
            cached.owner.m_Reports = 32
            cached.owner.HCRefuse('SYNTHETIC_REFUSAL')
            self.assertIs(status, cached.owner.HCStatus())
            self.assertEqual('refused', status.state)
            cached.owner.HCClose()
            self.assertEqual('off', status.state)

        with self.subTest(hc49='runtime ownership and durable story offer contract'):
            from tests.unit.test_hc_wildlife_wiring import method
            module = (SOURCE.parent / 'HCEcologyRuntimeModule.c').read_text()
            self.assertIn('protected ref HCWildlifeScenes m_WildlifeScenes;', module)
            self.assertIn('protected static HCEcologyRuntimeModule s_Instance;', module)
            start = method(module, 'HCEcologyRuntimeModule', 'OnStart')
            tick = method(module, 'HCEcologyRuntimeModule', 'OnTick')
            stop = method(module, 'HCEcologyRuntimeModule', 'OnStop')
            self.assertIn('m_WildlifeScenes.HCOpen(true)', start)
            self.assertIn('s_Instance = this;', start)
            self.assertIn('HCGroupClock.Utc()', tick)
            self.assertIn('if (utc < 1577836801) { return; }', tick)
            self.assertIn('m_WildlifeScenes.HCStep(utc - 1577836800, GetGame().GetTime())', tick)
            self.assertLess(stop.index('m_WildlifeScenes.HCClose()'), stop.index('m_WildlifeScenes = null'))
            self.assertIn('s_Instance = null;', stop)
            self.assertIn('return m_Status;', method(module, 'HCEcologyRuntimeModule', 'HCGetOperationalStatus'))
            self.assertIn('return s_Instance.m_WildlifeScenes;', method(module, 'HCEcologyRuntimeModule', 'HCWildlife'))
            scenes = (SOURCE.parent.parent / 'Scenes/HCScenesModule.c').read_text()
            step = method(scenes, 'HCScenesModule', 'StoryStep')
            self.assertLess(step.index('int nextSequence ='), step.index('m_Stories.HCStep(now, released)'))
            self.assertLess(step.index('SaveBarrierDone();'), step.index('wildlife.HCOffer('))
            self.assertIn('m_State.Stories.NextSequence != nextSequence', step)
            self.assertIn('arrived.StorySequence == m_State.Stories.NextSequence - 1', step)
            self.assertIn('HCEcologyRuntimeModule.HCWildlife()', step)
            self.assertIn('if (wildlife)', step)
            check_carcass_runtime(self)


if __name__ == '__main__':
    unittest.main()
