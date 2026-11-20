"""#135 review regressions: authored control flow, synthetic native ports only.

No fixture here establishes DayZ visibility, persistence or population behaviour.
"""
import math
import re
import unittest
from types import SimpleNamespace as NS

from tests.legacy.test_event_runtime import translate
from tests.legacy.test_group_server import EArray
from tests.legacy.test_infected_lod import SERVICE, STORE, source, policy


def authored(text, name, env, member=True):
    # Syntax adapters only: custom type declarations and increment operators.
    text = re.sub(r'\b(?:HCLOD\w*|HCInfected\w*|HCSettings|Man|PlayerBase)\s+(?=\w+\s*[=(;])', 'HCEventHandle ', text)
    text = re.sub(r'\b([\w.]+)\+\+', r'\1 += 1', text)
    text = re.sub(r'\b([\w.]+)--', r'\1 -= 1', text)
    text = re.sub(r'for \(int (\w+) = ([^;]+); \1 >= 0; \1 -= 1\)',
                  r'foreach (int \1 : reverse_indices(\2))', text)
    if member:
        text = re.sub(r'(?<![\w.])(CanRecycleActor|ResetSweep)\(', r'self.\1(', text)
    return translate(text, name, env, owner='AuthoredLOD', member=member)


def tracker(actors):
    text = source(SERVICE).split('modded class HCInfectedModule', 1)[1].split('class HCInfectedLODModule', 1)[0]
    env = dict(Math=NS(Min=min, Max=max), EArray=EArray, len=len, str=str,
               reverse_indices=lambda n: range(n, -1, -1), HCLODPolicy=policy(), HCInfectedLOD=NS(MAX_TOMBSTONES=24))
    cls = type('AuthoredTracker', (), {})
    for name in re.findall(r'\b(?:int|void) (HCLOD\w+)\(', text):
        if name in ('HCLODClassify', 'HCLODCounts', 'HCLODDescribe'): continue
        setattr(cls, name, authored(text, name, env))
    t = cls()
    t.m_Healthy = True
    t.m_Actors = EArray(actors)
    t.m_HCLODTombstones = EArray()
    t.m_HCLODCursor = 0
    t.m_Cursor = 0
    t.m_AdoptionCursor = 0
    t.m_RecoveryCursor = 0
    t.CanRecycleActor = lambda a: a.GroupId == 0
    t.ResetSweep = lambda: None
    return t


def actor(alive=False, group=0):
    return NS(InfectedEntity=NS(IsAlive=lambda: alive), GroupId=group, SearchPack=None)


class TombstoneCapacity(unittest.TestCase):
    def test_dead_slots_leave_live_capacity_and_archive_evicts_oldest(self):
        dead = [actor() for _ in range(24)]
        t = tracker(dead)
        self.assertEqual(0, t.HCLODTracked(), 'dead slots must not block herd materialization')
        self.assertEqual([], t.m_Actors)
        self.assertEqual(dead, t.m_HCLODTombstones)
        for _ in range(5):
            latest = [actor() for _ in range(24)]
            t.m_Actors.extend(latest)
            self.assertEqual(0, t.HCLODTracked())
            self.assertEqual(latest, t.m_HCLODTombstones, 'separate 24-entry FIFO, no unbounded history')
        living = actor(True)
        t.m_Actors.Insert(living)
        self.assertEqual(1, t.HCLODTracked())
        self.assertEqual([living], t.m_Actors)

    def test_fold_retires_its_live_slot_before_native_deletion(self):
        folded = actor(True)
        other = actor(True)
        t = tracker([folded, other])
        t.HCLODRetire(folded.InfectedEntity)
        self.assertEqual([other], t.m_Actors)
        self.assertEqual([folded], t.m_HCLODTombstones)
        self.assertEqual(1, t.HCLODTracked())

    def test_unresolved_horde_evidence_is_not_evicted(self):
        reserved = actor(False, group=1)
        t = tracker([actor(), reserved, actor(True)])
        t.HCLODTracked()
        self.assertIn(reserved, t.m_Actors, 'recovery owns unresolved assigned evidence')
        self.assertNotIn(reserved, t.m_HCLODTombstones)


class Vec(list):
    def __add__(self, other):
        if isinstance(other, str): other = [float(v) for v in other.split()]
        return Vec(a + b for a, b in zip(self, other))
    def __sub__(self, other): return Vec(a - b for a, b in zip(self, other))
    def __mul__(self, scale): return Vec(a * scale for a in self)


def sight_fixture(clear_call=None):
    text = source(SERVICE).split('class HCInfectedLOD\n', 1)[1].split('modded class ZombieBase', 1)[0]
    text = text.replace('set<Object>', 'array<Object>').replace('new array<Object>;', 'new array<Object>();')
    env = dict(Math=NS(Sqrt=math.sqrt), EArray=EArray, len=len, str=str,
               Vector=lambda *v: Vec(v), PlayerBase=NS(Cast=lambda p: p),
               vector=NS(Distance=lambda a, b: math.dist(a, b)),
               ObjIntersectView=1, ObjIntersectFire=0)
    # Make bare vector output parameters mutable, just as native out parameters.
    text = re.sub(r'\bvector (contact|normal);', r'vector \1 = Vector(0, 0, 0);', text)
    owner = NS()
    env['HCInfectedLOD'] = owner
    calls = []
    def ray(eye, aim, contact, normal, component, hits, *args):
        calls.append((list(eye), list(aim)))
        contact[:] = [(a + b) / 2 for a, b in zip(eye, aim)]
        return len(calls) != clear_call
    env['DayZPhysics'] = NS(RaycastRV=ray)
    for name in ('Blocked', 'RayBlocked', 'SightAim', 'Occluded'):
        if re.search(r'\b' + name + r'\(', text):
            setattr(owner, name, authored(text, name, env, member=False))
    if 'HCLODSightBudget budget' not in text:
        old_occluded = owner.Occluded
        owner.Occluded = lambda player, target, body, budget: old_occluded(player, target, body)
    player = NS(GetParent=lambda: None, GetPosition=lambda: Vec([0, 0, 0]),
                GetBoneIndexByName=lambda name: 0,
                GetBonePositionWS=lambda index: Vec([0, 1.7, 0]))
    return owner, player, calls


class PartialVisibility(unittest.TestCase):
    def test_any_clear_sample_refuses_even_when_chest_is_occluded(self):
        for clear_call in range(1, 7):
            with self.subTest(clear_call=clear_call):
                owner, player, calls = sight_fixture(clear_call=clear_call)
                budget = NS(Limit=12, Used=0)
                self.assertFalse(owner.Occluded(player, Vec([200, 0, 0]), None, budget),
                                 'any clear head/chest/offset geometry must veto')
                self.assertEqual(clear_call, len(calls))

    def test_all_three_samples_and_both_geometries_must_be_blocked(self):
        owner, player, calls = sight_fixture()
        budget = NS(Limit=12, Used=0)
        self.assertTrue(owner.Occluded(player, Vec([200, 0, 0]), None, budget))
        self.assertEqual(6, len(calls))
        self.assertEqual(3, len({tuple(aim) for eye, aim in calls}))
        self.assertEqual(6, budget.Used)
        self.assertTrue(owner.Occluded(player, Vec([200, 0, 0]), None, budget))
        self.assertFalse(owner.Occluded(player, Vec([200, 0, 0]), None, budget), 'exhaustion is unknown sight')
        self.assertEqual(12, len(calls), 'a 12-cast budget covers exactly two fully occluded observers')

    def test_incomplete_budget_and_vehicle_observers_refuse(self):
        owner, player, calls = sight_fixture()
        budget = NS(Limit=5, Used=0)
        self.assertFalse(owner.Occluded(player, Vec([200, 0, 0]), None, budget))
        self.assertEqual(5, len(calls))
        player.GetParent = lambda: object()
        self.assertFalse(owner.Occluded(player, Vec([200, 0, 0]), None, budget))
        self.assertEqual(5, len(calls))


def lifecycle(leases, alive=4, parked=None):
    text = source(SERVICE).split('class HCInfectedLODModule : HCModule', 1)[1].split('class HCInfectedLODContributor', 1)[0]
    text = text.replace('s_Instance', 'm_Instance')
    herd = NS(Alive=alive, UpdatedUtc=10)
    store = NS(NowUtc=lambda: 20, MarkDirty=lambda: None, Find=lambda herd_id: herd)
    store.Stop = lambda: setattr(store, 'saved', herd.Alive)
    if parked is None:
        parked = NS(leases=None)
        cache = source(SERVICE).split('class HCLODStopLeases', 1)[1].split('class HCInfectedLOD\n', 1)[0]
        cache = cache.replace('s_Leases', 'HCLODStopLeases.leases')
        cache = cache.replace('new array<ref HCLODLease>;', 'new array<ref HCLODLease>();')
        cache_env = dict(HCLODStopLeases=parked, EArray=EArray)
        for name in ('HCHold', 'HCTake'):
            setattr(parked, name, authored(cache, name, cache_env, member=False))
    infected = NS(HCLODClaimed=lambda body: body.claimed)
    env = dict(Math=NS(Max=max), EArray=EArray, len=len, str=str,
               reverse_indices=lambda n: range(n, -1, -1),
               HCInfectedModule=NS(Instance=infected), HCLODStopLeases=parked,
               HCInfectedLOD=NS(HCSet=lambda config: None),
               HCPerfPlayers=NS(HCGet=lambda: EArray()), GetGame=lambda: NS(GetTickTime=lambda: 100),
               HCDebugSnapshot=NS(HCUnregister=lambda d: None), HCLODPolicy=policy())
    cls = type('AuthoredLifecycle', (), {})
    for name in ('Herd', 'Debit', 'RemoveLease', 'HCLODPollLeases', 'OnStop', 'HCLODResume'):
        if re.search(r'\b' + name + r'\(', text):
            setattr(cls, name, authored(text, name, env))
    obj = cls()
    obj.m_Running = obj.m_Herds = True
    obj.m_Leases = EArray(leases)
    obj.m_Store = store
    obj.m_Debug = obj.m_Experiment = obj.m_Instance = None
    obj.m_LeaseCursor = obj.m_Deaths = obj.m_Vanished = obj.m_Released = 0
    obj.HCLODFoldDecision = lambda *args: 0  # explicit synthetic: body remains in view
    return obj, herd, store, parked


def lease(alive=True, claimed=False, missing=False):
    body = None if missing else NS(IsAlive=lambda: alive, claimed=claimed)
    return NS(Body=body, HerdId='synthetic-herd')


class StopAccounting(unittest.TestCase):
    def test_stop_preserves_living_heads_and_surviving_body_reservations(self):
        live = lease()
        obj, herd, store, parked = lifecycle([live], alive=3)
        obj.OnStop()
        self.assertEqual(3, store.saved, 'a living, visible member is still part of the herd')
        self.assertEqual([live], parked.leases, 'retained body occupies its slot after module restart')
        obj.m_Leases = EArray()
        obj.m_Store = store
        obj.HCLODResume()
        self.assertEqual([live], obj.m_Leases)
        self.assertIsNone(parked.leases)
        self.assertEqual([], parked.HCTake(), "a lease may be resumed only once")
        obj.m_Running = obj.m_Herds = True
        obj.OnStop()
        self.assertEqual(3, herd.Alive, 'repeated stop/start neither loses nor doubles a head')

    def test_dead_claimed_and_missing_members_are_reconciled_once(self):
        obj, herd, store, parked = lifecycle([lease(), lease(False), lease(claimed=True), lease(missing=True)])
        obj.OnStop()
        self.assertEqual(2, store.saved, 'only death and external ownership debit the living total')
        self.assertEqual(1, len(parked.leases))
        parked.leases[0].Body = None  # explicit engine deletion between stop/start
        obj.m_Leases = EArray()
        obj.m_Store = store
        obj.HCLODResume()
        obj.HCLODPollLeases(NS(HCLODClaimed=lambda body: False), 100)
        self.assertEqual(2, herd.Alive, 'vanished body returns to virtual data without a debit')
        self.assertEqual([], obj.m_Leases)


def lod_config():
    text = source(STORE).split('class HCInfectedLODConfig', 1)[1].split('class HCInfectedLODHerd\n', 1)[0]
    cfg = NS()
    for kind, key, value in re.findall(r'\b(int|float|bool|string) (\w+) = ([^;]+);', text):
        if kind == 'string': value = value.strip('"')
        elif kind == 'bool': value = value == 'true'
        else: value = float(value) if kind == 'float' else int(value)
        setattr(cfg, key, value)
    cfg.MemberTypes = EArray()
    cfg.Herds = EArray()
    return cfg, text


class DistanceBands(unittest.TestCase):
    def test_defaults_keep_the_documented_kilometre_bubble_in_simulation(self):
        cfg, text = lod_config()
        self.assertEqual(300, cfg.FullRange)
        self.assertEqual(1000, cfg.IdleRange)
        self.assertEqual(900, cfg.MaterializeRange)
        self.assertEqual(1000, cfg.FoldRange)
        self.assertEqual(1500, cfg.VisibilityRange)
        self.assertTrue(cfg.EnableVirtualHerds)
        p = policy()
        self.assertEqual(p.TIER_FULL, p.Tier(300, cfg.FullRange, cfg.IdleRange))
        self.assertEqual(p.TIER_IDLE, p.Tier(1000, cfg.FullRange, cfg.IdleRange))
        self.assertEqual(p.TIER_VIRTUAL, p.Tier(1001, cfg.FullRange, cfg.IdleRange))
        self.assertTrue(p.ValidRanges(cfg.FullRange, cfg.IdleRange, cfg.MinSpawnDistance,
                                      cfg.MaterializeRange, cfg.FoldRange, cfg.VisibilityRange))

    def test_config_rejects_bands_outside_transition_and_sight_ranges(self):
        cfg, text = lod_config()
        # Only for-loop syntax is adapted; empty synthetic seed/type arrays.
        text = re.sub(r'for \(int (\w+) = 0; \1 < ([^;]+); \1\+\+\)',
                      r'foreach (int \1 : indices(\2))', text)
        # The translator only prefixes native member fields named m_*.
        fields = ('SchemaVersion', 'MemberTypes', 'Herds', 'FullRange', 'IdleRange',
                  'MinSpawnDistance', 'MaterializeRange', 'FoldRange', 'VisibilityRange',
                  'ClassifyPerTick', 'MaxMaterialized', 'MaxPerHerd', 'PosedBudget',
                  'PosedFullBudget', 'PosedIdleBudget', 'MaxObservers', 'RegrowSeconds', 'HerdWorld', 'VarietyNonCalmHoldSeconds')
        for field in fields:
            text = re.sub(r'(?<![\w.])' + field + r'\b', 'm_' + field, text)
        valid = authored(text, 'IsValid', dict(HCLODPolicy=policy(), indices=range,
                                               HCInfectedVarietyPolicy=NS(ValidNonCalmHold=lambda seconds: 30 <= seconds <= 3600)))
        def evaluate(cfg):
            obj = NS(**{'m_' + key: getattr(cfg, key) for key in fields})
            return valid(obj)
        self.assertTrue(evaluate(cfg))
        for field, value in (('FullRange', 0), ('IdleRange', 2001), ('VisibilityRange', 3001),
                             ('IdleRange', 1600), ('FoldRange', 999), ('MaterializeRange', 299)):
            bad, _ = lod_config()
            setattr(bad, field, value)
            with self.subTest(field=field, value=value): self.assertFalse(evaluate(bad))


class FollowupWiring(unittest.TestCase):
    def test_tick_budget_stats_and_startup_ranges_are_connected(self):
        text = source(SERVICE)
        # Review P2: proving one observer occluded costs 3 samples x 2 geometries,
        # so the per-attempt budget must cover every allowed observer.
        self.assertIn('static const int RAYS_PER_OBSERVER = 6;', text)
        self.assertIn('m_Sight.HCReset(m_Config.MaxObservers * HCInfectedLOD.RAYS_PER_OBSERVER)', text)
        self.assertIn('(m_Config.MaxObservers * HCInfectedLOD.RAYS_PER_OBSERVER).ToString()', text)
        self.assertNotIn('MaxObservers * 2', text)
        self.assertIn('m_Rays += m_Sight.Used', text)
        for field in ('rays_per_min=', 'ray_peak=', 'ray_budget=', 'materialize<=', 'fold>', 'sight<='):
            self.assertIn(field, text)
        self.assertIn('if (m_Herds) { HCLODResume(); }', text)
        fold = text.split('protected void HCLODFold(int index', 1)[1].split('protected int HCLODFoldDecision', 1)[0]
        self.assertLess(fold.index('HCLODRetire(body)'), fold.index('ObjectDelete(body)'))
