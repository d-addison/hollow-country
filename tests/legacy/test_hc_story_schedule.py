"""HC-19 behavioral receipt: execute authored Enforce through restricted ports.

All state, cleanup receipts, clocks and disk images below are SYNTHETIC. No
engine persistence, placement, corpse/cargo or runtime acceptance is established.
Spec/plan/task: HC-19 / #147, independent arrivals; HC-10/HC-18 consumption
belongs to the lead. Round 2 integrates HCScenesModule in this worktree.
Actual receipt, 2026-11-18:
  PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=.:tests/unit python3 -m unittest test_hc_story_schedule -v
  RED: AssertionError: False is not true : fifth independent story rejected: no authored durable scheduler
  Ran 1 test; FAILED (failures=1).
  Follow-up RED: AttributeError: 'types.SimpleNamespace' object has no attribute 'HCIdentity'
  Follow-up RED: AssertionError: 100 != 1000 : migration must retain downtime evidence for owner ResumeAfterGap
  GREEN: same command; Ran 1 test; OK. World time is UTC since 2020,
including downtime; visual-season running-server time is deliberately separate.
"""
import copy
import functools
import json
from pathlib import Path
import re
from types import SimpleNamespace as N
import unittest

from tests.legacy.test_event_runtime import translate, environment
from tests.legacy.test_group_server import EArray, body
from tests.legacy.test_hc_unit_budget import unit_budget

ROOT = Path(__file__).resolve().parents[2]
SCENES = ROOT / 'mods/HollowCountry/scripts/4_World/Scenes'
SOURCE = SCENES / 'HCStorySchedule.c'


def bind(kind, target, env, names=None, member=False, path=SOURCE):
    text = path.read_text()
    match = re.search(r'class ' + kind + r'\s*\{', text)
    text = body(text, match.end())
    # Syntax adaptation only, using the existing restricted execution port.
    text = re.sub(r'\bHC(?:Story|Scene)\w*\b', lambda m: 'HCEvent' + m[0][2:], text)
    text = re.sub(r'for \(int (\w+) = 0; \1 < ([^;]+); \1\+\+\)',
                  r'foreach (int \1 : range(\2))', text)
    owner = 'HCEvent' + kind[2:]
    for name in names or re.findall(r'\b(?:bool|int|string|void|HCEvent\w+) (\w+)\(', text):
        fn = translate(text, name, env, owner, member=member)
        setattr(target, name, functools.partial(fn, target) if member else fn)
    return target


def dto(kind, env, path=SOURCE):
    """Instantiate authored DTO field defaults; syntax scaffolding only."""
    source = path.read_text()
    match = re.search(r'class ' + kind + r'\s*\{', source)
    fields = body(source, match.end())
    value = N()
    for field in re.finditer(r'^\s*(?:ref )?([\w<> ]+?) (\w+)(?:\s*=\s*([^;]+))?;', fields, re.M):
        typ, name, initializer = field.groups()
        if initializer and initializer.startswith('new array<'):
            default = EArray()
        elif initializer and initializer.startswith('new '):
            default = env[initializer[4:].strip()]()
        elif initializer:
            default = json.loads(initializer)
        elif typ == 'int':
            default = 0
        elif typ == 'string':
            default = ''
        else:
            default = None
        setattr(value, name, default)
    return value


class StoryScheduleBehavior(unittest.TestCase):
    def test_operator_off_legacy_state_saves_object_then_migrates_once(self):
        env = dict(EArray=EArray, str=str, Print=lambda line: None,
                   HCV2Admission=N(Admitted=lambda preference: preference),
                   HCEventDirector=N(TextValid=lambda text, limit: bool(text) and len(text) <= limit),
                   HCEventSceneChains=N(LoadCatalog=lambda: N(Chains=EArray())))
        env['HCStoryProgress'] = lambda: dto('HCStoryProgress', env)
        env['HCEventStoryProgress'] = env['HCStoryProgress']
        state = dto('HCSceneChainState', env, SCENES / 'HCSceneChains.c')
        self.assertIsNotNone(state.Stories, 'legacy Stories must serialize as an object, never null')
        state.LastNow = 100
        state.Chains = EArray([N(Id='synthetic-legacy', StorySequence=0, Complete=False, Cancelled=False)])
        policy = N()
        env['HCEventStoryPolicy'] = policy
        bind('HCStoryPolicy', policy, env,
             names=['HCConfigValid', 'HCUnmigrated', 'HCValid', 'HCMigrate', 'HCIdentity'])
        self.assertTrue(policy.HCValid(state))
        self.assertTrue(policy.HCUnmigrated(state.Stories))
        images = []
        store = N(Save=lambda value: images.append(copy.deepcopy(value)) or True)
        config = N(Version=1, EnableStories=False, ArrivalSeconds=21600, Window=4)
        schedule = N(m_Ready=False, m_Reason='', m_State=None)
        bind('HCStorySchedule', schedule, env, member=True)
        # Legacy DTOs supplied by old tools can still have an explicit null.
        state.Stories = None
        self.assertFalse(schedule.HCStart(state, store, config, 1000, True))
        self.assertEqual('operator-off', schedule.HCReason())
        self.assertEqual([], images, 'off path must not migrate or save')
        self.assertIsNotNone(state.Stories)
        self.assertEqual(0, state.Chains[0].StorySequence)
        serialized = json.dumps(state, default=vars)
        self.assertIsInstance(json.loads(serialized)['Stories'], dict)
        reopened = copy.deepcopy(state)  # explicit synthetic loader port
        self.assertTrue(policy.HCValid(reopened))
        config.EnableStories = True
        self.assertTrue(schedule.HCStart(reopened, store, config, 1000, True))
        self.assertEqual(1, len(images))
        self.assertEqual((1, 2, 100), (reopened.Stories.LegacyThrough,
                         reopened.Stories.NextSequence, reopened.LastNow))
        self.assertTrue(policy.HCValid(reopened))
        schedule.HCStop()
        self.assertTrue(schedule.HCStart(reopened, store, config, 1010, True))
        self.assertEqual(1, len(images), 'already migrated restart must not reissue identities')
        # An object with partially populated history is corruption, not legacy.
        for field, value in (('NextSequence', 2), ('NextArrival', 1),
                             ('TerminalThrough', 1), ('Version', 2),
                             ('LegacyIds', EArray(['forged'])),
                             ('TerminalExceptions', EArray([1]))):
            with self.subTest(field=field):
                bad = copy.deepcopy(state)
                setattr(bad.Stories, field, value)
                self.assertFalse(policy.HCValid(bad))

    def test_independent_successors_migration_failed_start_and_restart_conservation(self):
        self.assertTrue(SOURCE.exists(), 'fifth independent story rejected: no authored durable scheduler')
        logs = []
        config = N(**json.loads((ROOT / 'config/hollow-country-stories.json').read_text()))
        # Four existing pinned plans and states, including an unfinished old scene.
        def stage(kind):
            return N(Kit=kind, HoldSeconds=7200, DelaySeconds=3600,
                     Objective=N(LifetimeSeconds=43200, Radius=25, DwellSeconds=20,
                                 MaxParticipants=3, AnchorClass=''))

        plans = EArray([N(Id='legacy-' + str(i), SiteId='synthetic-site-' + str(i),
                          Stages=EArray([stage(k) for k in ('synthetic-a', 'synthetic-b', 'synthetic-c')]))
                        for i in range(4)])
        templates = copy.deepcopy(plans)
        chains = EArray([N(Id=p.Id, StorySequence=0, Complete=i != 0, Cancelled=False,
                           Stage=0, DueAt=100, ExpiresAt=200, BeganAt=123,
                           Director=N(Session=p.Id, Records=EArray([N(Cargo='old finite cargo')])) )
                         for i, p in enumerate(plans)])
        state = N(Stories=None, LastNow=100, WorldName='chernarusplus', Chains=chains,
                  Catalog=N(Chains=plans))
        images = []
        fail = [False]

        def save(value):
            if fail[0]:
                return False
            images.append(copy.deepcopy(value))
            return True

        env = dict(EArray=EArray, str=str, Print=logs.append,
                   HCV2Admission=N(Admitted=lambda preference: preference),
                   HCEventStoryProgress=lambda: N(Version=1, NextSequence=1, LegacyThrough=0,
                       TerminalThrough=0, TerminalExceptions=EArray(), LegacyIds=EArray(), NextArrival=0),
                   HCEventSceneChain=lambda: N(Id='', StorySequence=0, Complete=False,
                       Cancelled=False, Director=None, Stage=0),
                   HCEventDirector=N(Initialize=lambda world, key: N(Session=key),
                       TextValid=lambda text, limit: bool(text) and len(text) <= limit),
                   HCEventSceneChains=N(LoadCatalog=lambda: copy.deepcopy(N(Chains=templates)),
                       Plan=lambda key, site, a, b, c: N(Id=key, SiteId=site,
                           Stages=EArray([stage(k) for k in (a, b, c)])),
                       Schedule=lambda row, stage, now: setattr(row, 'DueAt', now)),
                   GetGame=lambda: N(GetTickTime=lambda: 1.))
        policy = N()
        env['HCEventStoryPolicy'] = policy
        bind('HCStoryPolicy', policy, env, names=['HCConfigValid', 'HCUnmigrated', 'HCValid', 'HCMigrate', 'HCRetired', 'HCIdentity', 'HCPlan'])

        def scheduler(value):
            obj = N(m_State=value, m_Store=N(Save=save), m_Config=config, m_Ready=False,
                    m_Reason='', m_Cursor=0, m_Units=unit_budget(),
                    m_Work=N(HCReset=lambda *args: None, HCContinue=lambda: True))
            bind('HCStorySchedule', obj, env, member=True)
            return obj

        migration = scheduler(copy.deepcopy(state))
        self.assertTrue(migration.HCStart(migration.m_State, migration.m_Store, config, 1000, True))
        self.assertEqual(100, migration.m_State.LastNow,
                         'migration must retain downtime evidence for owner ResumeAfterGap')
        owner = scheduler(state)
        pinned = copy.deepcopy(chains[0])
        self.assertTrue(owner.HCStart(state, owner.m_Store, config, 100, True))
        self.assertEqual(5, state.Stories.NextSequence)
        self.assertEqual(vars(pinned), vars(N(**{**vars(chains[0]), 'StorySequence': 0})))
        self.assertTrue(policy.HCValid(state))
        self.assertEqual([], state.Stories.TerminalExceptions)
        self.assertEqual('legacy-0', owner.HCCandidate().Id)
        self.assertEqual('hc-story-5-n-n', policy.HCIdentity(5, EArray(['hc-story-5', 'hc-story-5-n'])))
        # A terminal chain still leased to the owner cannot be paged out.
        for _ in range(4):
            owner.HCStep(101, EArray())
        self.assertEqual(4, len(state.Chains))
        # Out-of-order completion fits bounded exceptions; no old ID is revived.
        owner.HCStep(102, EArray(['legacy-1', 'legacy-2', 'legacy-3']))
        owner.HCStep(103, EArray(['legacy-1', 'legacy-2', 'legacy-3']))
        owner.HCStep(104, EArray(['legacy-1', 'legacy-2', 'legacy-3']))
        owner.HCStep(105, EArray(['legacy-1', 'legacy-2', 'legacy-3']))
        self.assertEqual([2, 3, 4], sorted(state.Stories.TerminalExceptions))
        self.assertEqual(0, state.Stories.TerminalThrough)
        self.assertTrue(policy.HCValid(state))
        due = state.Stories.NextArrival
        owner.HCStep(due, EArray())
        self.assertEqual(5, state.Stories.NextSequence, 'bounded window stalls behind pinned oldest')
        state.Chains[0].Cancelled = True  # synthetic failed start/expiry receipt
        owner.HCStep(due + 1, EArray(['legacy-0']))
        self.assertEqual(4, state.Stories.TerminalThrough)
        # Arrival may happen in the next retained-cursor slice.
        owner.HCStep(due + 2, EArray())
        self.assertEqual('hc-story-5', state.Chains[0].Id)
        self.assertEqual(6, state.Stories.NextSequence)
        self.assertNotEqual('legacy-0', state.Catalog.Chains[0].Id)
        self.assertEqual(3, state.Catalog.Chains[0].Stages[0].Objective.MaxParticipants)
        self.assertTrue(policy.HCValid(state))
        # Delayed start, save/restart and a failed start conserve the reserved ID.
        restarted = copy.deepcopy(images[-1])
        owner = scheduler(restarted)
        self.assertTrue(owner.HCStart(restarted, owner.m_Store, config, due + 999, True))
        self.assertEqual('hc-story-5', restarted.Chains[0].Id)
        self.assertEqual(6, restarted.Stories.NextSequence)
        restarted.Chains[0].Cancelled = True
        owner.HCStep(due + 1000, EArray(['hc-story-5']))
        self.assertEqual(5, restarted.Stories.TerminalThrough)
        next_due = restarted.Stories.NextArrival
        owner.HCStep(next_due, EArray())
        self.assertEqual('hc-story-6', restarted.Chains[0].Id)
        # Failed durable reservation refuses further work; reopening last image
        # retains the same next sequence, never issuing cargo on the failed path.
        restarted.Chains[0].Cancelled = True
        fail[0] = True
        owner.HCStep(next_due + 1, EArray(['hc-story-6']))
        self.assertFalse(owner.HCReady())
        before = copy.deepcopy(restarted)
        owner.HCStep(next_due + config.ArrivalSeconds, EArray(['hc-story-6']))
        self.assertEqual(vars(before.Stories), vars(restarted.Stories))
        self.assertIn('save-failed', owner.HCReason())
        fail[0] = False
        disk = copy.deepcopy(images[-1])
        self.assertEqual('hc-story-6', disk.Chains[0].Id)
        self.assertFalse(disk.Chains[0].Cancelled)
        # A failed reservation creates no materialization permission; restart
        # uses the last disk sequence. This port does no object/inventory work.
        reservation = copy.deepcopy(disk)
        reservation.Chains[0].Cancelled = True
        owner = scheduler(reservation)
        self.assertTrue(owner.HCStart(reservation, owner.m_Store, config, next_due, True))
        owner.HCStep(next_due + 1, EArray(['hc-story-6']))
        conserved = copy.deepcopy(images[-1])
        fail[0] = True
        owner.HCStep(conserved.Stories.NextArrival, EArray())
        self.assertFalse(owner.HCReady())
        self.assertEqual(7, images[-1].Stories.NextSequence)
        fail[0] = False
        owner = scheduler(copy.deepcopy(conserved))
        self.assertTrue(owner.HCStart(owner.m_State, owner.m_Store, config,
                                     conserved.Stories.NextArrival, True))
        owner.HCStep(conserved.Stories.NextArrival, EArray())
        self.assertEqual('hc-story-7', owner.m_State.Chains[0].Id)
        self.assertEqual(8, owner.m_State.Stories.NextSequence)
        # Two-stage operator seeds remain two-stage, with unique objectives.
        two = copy.deepcopy(N(Chains=templates))
        for seed in two.Chains:
            seed.Stages.pop()
        generated = policy.HCPlan(8, two, state.Stories.LegacyIds)
        self.assertEqual(2, len(generated.Stages))
        self.assertEqual(2, len({s.Kit for s in generated.Stages}))
        # Off does not migrate, scan or save. Rewinds fail closed.
        off = scheduler(disk)
        count = len(images)
        self.assertFalse(off.HCStart(disk, off.m_Store, config, next_due, False))
        off.HCStep(next_due + 1, EArray())
        self.assertEqual(count, len(images))
        owner = scheduler(disk)
        self.assertTrue(owner.HCStart(disk, owner.m_Store, config, next_due, True))
        owner.HCStep(disk.LastNow - 1, EArray())
        self.assertFalse(owner.HCReady())
        owner.HCStop()
        self.assertFalse(owner.HCReady())
        self.assertTrue(any('HC-19' in line and 'terminal_replay=0' in line and 'runtime=PENDING' in line for line in logs))
        # Corrupt duplicate/replayed/missing identities refuse, never reset history.
        for mutate in (lambda s: setattr(s.Chains[0], 'StorySequence', 1),
                       lambda s: setattr(s.Stories, 'NextSequence', 99),
                       lambda s: s.Stories.TerminalExceptions.Insert(s.Chains[0].StorySequence)):
            bad = copy.deepcopy(disk)
            mutate(bad)
            self.assertFalse(policy.HCValid(bad))

        # Execute the actual plan builder AND shared state validator, with only
        # DTO constructors and native handles supplied by the established port.
        native = environment()
        native['Print'] = logs.append
        native['HCEventStoryPolicy'] = policy
        native['HCEventReviewedSites'] = N()
        reviewed = (SCENES.parent / 'Events/HCEventReviewedSites.c').read_text()
        for name in ('Build', 'Curated', 'SceneMission'):
            setattr(native['HCEventReviewedSites'], name,
                    translate(reviewed, name, native, 'HCEventReviewedSites'))
        native['HCEventSceneCatalog'] = lambda: N(Version=1, Chains=EArray())
        native['HCEventSceneChainDefinition'] = lambda: N(Id='', SiteId='', Stages=EArray())
        native['HCEventSceneStageDefinition'] = lambda: N(Kit='', HoldSeconds=21600,
                                                          DelaySeconds=21600, Objective=None)
        native['HCEventSceneKits'] = N(Reviewed=lambda site: site is not None,
                                       Find=lambda kind: kind)  # synthetic geometry/class port
        chain_policy = N()
        native['HCEventSceneChains'] = chain_policy
        bind('HCSceneChains', chain_policy, native,
             names=['Plan', 'Defaults', 'Site', 'CatalogValid', 'Schedule', 'StateValid'],
             path=SCENES / 'HCSceneChains.c')
        actual_policy = N()
        native['HCEventStoryPolicy'] = actual_policy
        bind('HCStoryPolicy', actual_policy, native,
             names=['HCUnmigrated', 'HCValid', 'HCPlan', 'HCRetired', 'HCIdentity'])
        seeds = chain_policy.Defaults()
        self.assertTrue(chain_policy.CatalogValid(seeds, False))
        plan = actual_policy.HCPlan(5, seeds, EArray(p.Id for p in seeds.Chains))
        arrived = N(Id=plan.Id, StorySequence=5, Stage=0, EventId=0,
                    DueAt=0, ExpiresAt=0, BeganAt=0, Complete=False, Cancelled=False,
                    Director=native['HCEventDirector'].Initialize('chernarusplus', plan.Id))
        chain_policy.Schedule(arrived, plan.Stages[0], 100)
        progress = N(Version=1, NextSequence=6, TerminalThrough=4, LegacyThrough=4,
                     TerminalExceptions=EArray(), LegacyIds=EArray(p.Id for p in seeds.Chains), NextArrival=1000)
        actual_state = N(Version=1, Revision=0, WorldName='chernarusplus', LastNow=100,
                         Stories=progress, Chains=EArray([arrived]),
                         Catalog=N(Version=1, Chains=EArray([plan])))
        self.assertTrue(chain_policy.StateValid(actual_state))
        self.assertEqual(0, plan.Stages[0].Objective.RewardUnits)
        self.assertEqual('', plan.Stages[0].Objective.ItemClass)
        self.assertFalse(plan.Stages[0].Objective.RewardCache)
        # Empty rolling page is valid between retirement and next arrival.
        actual_policy.HCRetired(progress, 5)
        actual_state.Chains.Clear()
        actual_state.Catalog.Chains.Clear()
        self.assertTrue(chain_policy.StateValid(actual_state))
        self.assertFalse(chain_policy.CatalogValid(actual_state.Catalog, False))
