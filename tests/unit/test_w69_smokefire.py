"""W69 source-body tests with explicit synthetic native observations; no DayZ proof."""
from pathlib import Path
from types import SimpleNamespace as N
import re
import unittest
from tests.unit.test_event_runtime import translate
from tests.unit.test_group_server import EArray

ROOT = Path(__file__).resolve().parents[2]
SIGNS = ROOT / 'mods/HollowCountry/scripts/4_World/Atmosphere/HCSignsOfLife.c'
HEARTH = SIGNS.with_name('HCHearthFires.c')
REGISTRY = ROOT / 'mods/HollowCountry/scripts/3_Game/Atmosphere/HCHearthSettingsRegistry.c'
CLIENT = ROOT / 'mods/HollowCountry/scripts/5_Mission/Atmosphere/HCSignsOfLifeClient.c'


class SmokeFireTests(unittest.TestCase):
    def smoke_policy(self, burning):
        source = SIGNS.read_text()
        policy = N(ForceLit=[], HouseHash=lambda pos, day: 0)
        env = dict(HCSignsOfLife=policy,
                   HCHearthFires=N(HCHasBurning=lambda house: burning))
        return translate(source, 'IsSmoke', env, 'HCSignsOfLife')

    def test_house_without_fire_never_selected_for_smoke(self):
        # Legacy hash=0 selected this empty synthetic house.
        self.assertFalse(self.smoke_policy(False)((100, 0, 200), 739937),
                         'smoke chosen for a house without a fire')

    def test_burning_observation_selects_smoke_without_daily_lottery(self):
        self.assertTrue(self.smoke_policy(True)((100, 0, 200), 739937))

    def test_no_fuel_refuses_before_creating_fire(self):
        self.assertTrue(HEARTH.exists(), 'missing funded hearth implementation')
        source = HEARTH.read_text()
        env = {}
        ready = translate(source, 'HCFuelReady', env)
        self.assertFalse(ready(None, None))
        self.assertFalse(ready(object(), None))
        self.assertFalse(ready(None, object()))
        self.assertTrue(ready(object(), object()))
        light = source[source.index('static bool HCLight('):]
        self.assertLess(light.index('HCFuelReady('), light.index('CreateObjectEx('))
        self.assertIn('HC_HEARTH_NO_FUEL', light)
        self.assertIn('ServerTakeEntityToTargetAttachment', light)
        self.assertNotIn('CreateInInventory', source)

    def test_no_synthetic_fire_effects_and_bounded_native_observation(self):
        source = CLIENT.read_text()
        self.assertNotIn('Particle.PlayInWorld(ParticleList.HOUSE_SMALL_SMOKE', source)
        self.assertNotIn('ScriptedLightBase.CreateLight(HCSignsWindowLight', source)
        hearth = HEARTH.read_text()
        for text in ('IsBurning()', 'MaxHearths', 'MaxObjects', 'HCPerfSlices',
                     'HCServer.HCTickWork()', 'HCJsonFields.Has', 'LitByKind',
                     'LitById', 'LitAt', 'runtime=PENDING', 'hearth-fires.disable'):
            self.assertIn(text, hearth)

    def test_live_fire_required_for_glow_and_holdout_occupancy_not_proof(self):
        env = dict(HCHearthFires=N(HCHasBurning=lambda house: False))
        predicate = translate(SIGNS.read_text(), 'IsLit', env)
        self.assertFalse(predicate(N(), 739937))
        select = SIGNS.read_text().split('static void SelectHouses', 1)[1].split('override void OnTick', 1)[0]
        self.assertIn('IsSmoke(candidate, day)', select)
        self.assertIn('IsLit(candidate, day)', select)


class NativeList(EArray):
    def GetItemCount(self): return len(self)
    def GetItem(self, index): return self[index]
    def Contains(self, key): return key in self


class NativeMap(dict):
    def Contains(self, key): return key in self
    def Count(self): return len(self)
    def Get(self, key): return self.get(key, 0)
    def Set(self, key, value): self[key] = value
    def GetKey(self, index): return list(self)[index]
    def Remove(self, key): del self[key]


class FundedIgnitionTests(unittest.TestCase):
    """Execute HCLight with synthetic native inventory, geometry and ignition ports."""
    def fixture(self, fuel=True):
        source = HEARTH.read_text()
        source = re.sub(r'\b(?:HCHearthConfig|FireplaceIndoor|FireplaceBase)\s+(?=\w+\s*[=;])', 'Object ', source)
        now, created, refusals, seen, hidden = [1000], [], [], [], [True]
        cfg = N(MaxHearths=4, AttemptSeconds=60, ActorRange=3, QueryRadius=30,
                MaxInventory=8, ObserverRadius=500, HearthsPerTick=2)
        class Item:
            def __init__(self, kind): self.kind, self.parent, self.used = kind, None, 0
            def GetType(self): return self.kind
            def IsRuined(self): return False
            def GetHierarchyParent(self): return self.parent
            def CanIgniteItem(self, target): return True
            def OnIgnitedTarget(self, target): self.used += 1
        paper, wood, matches = Item('Paper'), Item('Firewood'), Item('Matchbox')
        cargo = NativeList([paper, wood, matches] if fuel else [matches])
        attached = NativeList()
        class Fire:
            def __init__(self): self.burning = False
            def IsBurning(self): return self.burning
            def GetInventory(self):
                return N(AttachmentCount=lambda: len(attached), GetAttachmentFromIndex=lambda i: attached[i])
            def SetFirePointIndex(self, value): pass
            def SetSmokePointPosition(self, value): pass
            def SetOrientation(self, value): pass
            def Synchronize(self): pass
            def CanBeIgnitedBy(self, value): return paper in attached
            def IsThisIgnitionSuccessful(self, value): return True
            def OnIgnitedThis(self, value): self.burning = True
        def create(*args):
            result = Fire(); created.append(result); return result
        stash = N(GetPosition=lambda: [1, 0, 1], GetHierarchyRootPlayer=lambda: None,
                  GetInventory=lambda: N(GetCargo=lambda: cargo))
        def move(fire, item):
            self.assertIs(policy.s_Spending, stash, 'spend callback guard must bracket native transfer')
            cargo.remove(item); attached.append(item); item.parent = fire; return True
        stash.ServerTakeEntityToTargetAttachment = move
        house = N(GetSelectionPositionMS=lambda selection: [1, 0, 1],
                  ModelToWorld=lambda value: value, GetOrientation=lambda: [0, 0, 0])
        # SimpleNamespace is unhashable; synthetic building handle needs native identity hashing.
        class House:
            GetSelectionPositionMS = staticmethod(house.GetSelectionPositionMS)
            ModelToWorld = staticmethod(house.ModelToWorld)
            GetOrientation = staticmethod(house.GetOrientation)
        house = House()
        actor = N(IsAlive=lambda: True, GetPosition=lambda: [1, 0, 1])
        policy = N(s_Running=True, s_ReclaimFirst=False, s_AttemptCursor=0, s_Attempts=NativeMap(), s_Lit=EArray(), s_Spending=None,
                   s_Budget=N(HCReset=lambda n: None, HCContinue=lambda: True),
                   HCRefuse=lambda reason: refusals.append(reason) or False,
                   HCObserve=lambda fire, house: seen.append((fire, house)),
                   HCFindIndoor=lambda position: created[0] if created else None)
        env = dict(HCHearthFires=policy, HCHearthConfig=N(HCGet=lambda: cfg),
                   HCWorldClock=N(UTC=lambda: now[0]),
                   HCObserverTransitionGate=N(CanTransition=lambda *args: hidden[0]),
                   HCServer=N(HCTickWork=lambda: N(HCTake=lambda n: True, HCTakeFor=lambda consumer, n: True)),
                   HCUnitBudget=N(HC_WORK_HEARTH=16), Math=N(Min=min),
                   FireplaceIndoor=N(Cast=lambda value: value, CanPlaceFireplaceInSelectedSpot=lambda *a: True),
                   ItemBase=N(Cast=lambda value: value), GetGame=lambda: N(IsServer=lambda: True, CreateObjectEx=create),
                   vector=N(Zero=[0, 0, 0], DistanceSq=lambda a,b: sum((x-y)**2 for x,y in zip(a,b))),
                   ECE_KEEPHEIGHT=1, Print=lambda receipt: None)
        env["HCFindIndoor"] = policy.HCFindIndoor
        tick_source = source.replace('HCHoldouts holdouts', 'Object holdouts').replace('HCHearthRecord row', 'Object row')
        env['HCHoldouts'] = N(Get=lambda: None)
        # Static storage binding only; execute the authored tick control flow.
        tick_source = re.sub(r'(?<![\w.])(s_\w+)', r'HCHearthFires.\1', tick_source)
        for method in ('HCReclaimAttempts', 'HCWorkTick', 'HCTick'):
            if 'static void ' + method + '(' in tick_source:
                setattr(policy, method, translate(tick_source, method, env, 'HCHearthFires'))
        policy.HCFuelReady = translate(source, 'HCFuelReady', env, 'HCHearthFires')
        light = translate(source, 'HCLight', env, 'HCHearthFires')
        return N(light=lambda target=house: light(target, actor, stash, 'holdout', 'synthetic-home'),
                 cargo=cargo, created=created, refusals=refusals, paper=paper, wood=wood,
                 matches=matches, policy=policy, now=now, hidden=hidden, stash=stash, cfg=cfg, env=env, house=house)

    def test_reclamation_and_dispatch_progress_under_sustained_budget_exhaustion(self):
        from tests.unit.tick_budget_fixture import new_budget, constants
        f = self.fixture()
        work = new_budget()
        ids = constants()
        f.env['HCUnitBudget'] = N(**ids)
        f.env['HCServer'].HCTickWork = lambda: work
        f.policy.s_HoldoutCursor = 0
        dispatches = []
        f.env['HCHoldouts'].Get = lambda: N(Count=lambda: 1, HCHearthLight=dispatches.append)
        fresh = object()
        expired = [object() for _ in range(4)]
        f.cfg.MaxHearths = len(expired) + 1
        f.policy.s_Attempts.Set(fresh, f.now[0] + 1000)
        for house in expired:
            f.policy.s_Attempts.Set(house, f.now[0])
        for _ in range(120):
            work.HCReset(1)
            self.assertTrue(work.HCTakeFor(ids['HC_WORK_INFECTED'], 1))
            f.policy.HCTick()
            self.assertLessEqual(work.HCUsed(), 2, 'use only the existing forced hearth allowance')
            f.now[0] += 1
        self.assertEqual({fresh}, set(f.policy.s_Attempts), 'expired attempts must clear under sustained exhaustion')
        self.assertGreaterEqual(len(dispatches), 60, 'holdout dispatch must retain regular progress')

    def test_reclamation_does_not_starve_funded_holdout_with_two_units_left(self):
        from tests.unit.tick_budget_fixture import new_budget, constants
        f = self.fixture()
        work = new_budget()
        ids = constants()
        f.env['HCUnitBudget'] = N(**ids)
        f.env['HCServer'].HCTickWork = lambda: work
        f.policy.s_HoldoutCursor = 0
        f.policy.s_Attempts.Set(f.house, f.now[0])
        f.env['HCHoldouts'].Get = lambda: N(Count=lambda: 1, HCHearthLight=lambda index: f.light())
        for _ in range(180):
            work.HCReset(3)
            self.assertTrue(work.HCTakeFor(ids['HC_WORK_INFECTED'], 1))
            f.policy.HCTick()
            f.now[0] += 1
        self.assertEqual(1, len(f.created), 'funded holdout must ignite despite expired attempt reclamation')
        self.assertEqual(1, f.matches.used)

    def test_attempt_sweep_inspects_each_entry_only_once(self):
        f = self.fixture()
        f.cfg.HearthsPerTick = 4
        fresh = object()
        f.policy.s_Attempts.Set(object(), f.now[0])
        f.policy.s_Attempts.Set(fresh, f.now[0] + 60)
        inspected = []
        native_get_key = f.policy.s_Attempts.GetKey
        def get_key(index):
            key = native_get_key(index)
            inspected.append(key)
            return key
        f.policy.s_Attempts.GetKey = get_key
        f.policy.HCTick()
        self.assertEqual(2, len(inspected), 'a sweep must not revisit fresh entries after removing expired ones')
        self.assertEqual(2, len(set(inspected)))
        self.assertEqual({fresh}, set(f.policy.s_Attempts))

    def test_expired_attempts_allow_new_houses_past_lifetime_cap(self):
        f = self.fixture()
        old_houses = [type(f.house)() for _ in range(f.cfg.MaxHearths)]
        f.hidden[0] = False
        for house in old_houses:
            self.assertFalse(f.light(house))
            self.assertEqual('HC_HEARTH_OBSERVED', f.refusals[-1])
        f.hidden[0] = True
        self.assertFalse(f.light())
        self.assertEqual('HC_HEARTH_ATTEMPT_CAP', f.refusals[-1])
        f.now[0] += f.cfg.AttemptSeconds
        f.policy.HCTick()
        self.assertTrue(f.light(), 'expired attempt slots must admit a new funded house')
        self.assertLessEqual(len(f.policy.s_Attempts), f.cfg.MaxHearths)

    def test_attempt_sweep_is_bounded_budgeted_and_keeps_live_cooldowns(self):
        f = self.fixture()
        keys = [object() for _ in range(4)]
        for index, house in enumerate(keys):
            f.policy.s_Attempts.Set(house, f.now[0] + (60 if index < 2 else 0))
        calls, allowed = [], [False]
        def take(consumer, count):
            calls.append((consumer, count))
            return allowed[0]
        f.env['HCServer'].HCTickWork = lambda: N(HCTakeFor=take)
        f.policy.HCTick()
        self.assertEqual(0, f.policy.s_AttemptCursor)
        self.assertEqual(4, len(f.policy.s_Attempts))
        allowed[0] = True
        calls.clear()
        f.policy.HCTick()
        self.assertEqual([(16, 1)] * 2, calls)
        self.assertEqual(4, len(f.policy.s_Attempts), 'unexpired entries survive')
        calls.clear()
        f.policy.HCTick()
        self.assertEqual([(16, 1)] * 2, calls)
        self.assertEqual(set(keys[:2]), set(f.policy.s_Attempts))
        f.policy.s_Running = False
        calls.clear()
        f.policy.HCTick()
        self.assertEqual([], calls)

    def test_no_fuel_actual_ignition_path_preserves_inventory(self):
        f = self.fixture(fuel=False)
        self.assertFalse(f.light())
        self.assertEqual(['HC_HEARTH_NO_FUEL'], f.refusals)
        self.assertEqual([], f.created)
        self.assertEqual([f.matches], f.cargo)

    def test_real_items_transfer_once_and_match_is_spent(self):
        f = self.fixture()
        self.assertTrue(f.light())
        self.assertEqual([f.matches], f.cargo)
        self.assertIsNone(f.policy.s_Spending)
        self.assertEqual(1, f.matches.used)
        self.assertEqual('holdout', f.created[0].HCHearthLitKind)
        self.assertEqual('synthetic-home', f.created[0].HCHearthLitId)
        self.assertEqual(1000, f.created[0].HCHearthLitAt)
        f.now[0] += 61
        self.assertTrue(f.light())
        self.assertEqual(1, len(f.created))
        self.assertEqual(1, f.matches.used)

    def test_partial_transfer_retries_without_duplicate_fire_or_fuel(self):
        f = self.fixture()
        native_move = f.stash.ServerTakeEntityToTargetAttachment
        fail_wood = [True]
        def move(fire, item):
            if item is f.wood and fail_wood[0]:
                fail_wood[0] = False
                return False
            return native_move(fire, item)
        f.stash.ServerTakeEntityToTargetAttachment = move
        self.assertFalse(f.light())
        self.assertEqual(['HC_HEARTH_WOOD_TRANSFER_FAILED'], f.refusals)
        self.assertIsNone(f.policy.s_Spending)
        self.assertEqual(0, f.matches.used)
        f.now[0] += 61
        self.assertTrue(f.light())
        self.assertEqual(1, len(f.created))
        self.assertEqual([f.matches], f.cargo)
        self.assertEqual(1, f.matches.used)

    def test_visible_house_does_not_spend_or_create(self):
        f = self.fixture(); f.hidden[0] = False
        self.assertFalse(f.light())
        self.assertEqual(['HC_HEARTH_OBSERVED'], f.refusals)
        self.assertEqual(3, len(f.cargo))
        self.assertEqual([], f.created)


class NativeObservationTests(unittest.TestCase):
    def fixture(self, burning, server=False, cap=8):
        source = HEARTH.read_text()
        source = re.sub(r'\b(?:HCHearthConfig|FireplaceBase)\s+(?=\w+\s*[=;])', 'Object ', source)
        observed, objects = [], EArray()
        fires = [N(IsBurning=lambda value=value: value, GetHierarchyParent=lambda: None)
                 for value in burning]
        def query(center, radius, out_objects, out_cargos): out_objects.extend(fires)
        policy = N(HCEnabled=lambda: True, HCObserve=lambda fire, house: observed.append(fire),
                   HCContains=lambda house, fire: True)
        env = dict(HCHearthFires=policy, EArray=EArray,
                   HCHearthConfig=N(HCGet=lambda: N(QueryRadius=30, MaxObjects=cap, AnchorTolerance=.35)),
                   GetGame=lambda: N(GetObjectsAtPosition3D=query, IsServer=lambda: server),
                   FireplaceBase=N(Cast=lambda value: value), Math=N(Min=min),
                   vector=N(Zero=[0, 0, 0]))
        policy.HCMatches = translate(source, 'HCMatches', env, 'HCHearthFires')
        policy.HCHasBurning = translate(source, 'HCHasBurning', env, 'HCHearthFires')
        house = N(GetPosition=lambda: [10, 0, 20], GetSelectionPositionMS=lambda name: [0, 0, 0])
        return N(has=lambda: policy.HCHasBurning(house), observed=observed, fires=fires)

    def test_client_observes_live_burning_state_and_extinction(self):
        f = self.fixture([False, True])
        self.assertTrue(f.has())
        self.assertEqual([], f.observed, 'client must not author server provenance')
        f.fires[1].IsBurning = lambda: False
        self.assertFalse(f.has())

    def test_query_prefix_cap_never_infers_unobserved_fire(self):
        f = self.fixture([False, True], cap=1)
        self.assertFalse(f.has())

    def test_server_binds_only_burning_native_fire(self):
        f = self.fixture([False, True], server=True)
        self.assertTrue(f.has())
        self.assertEqual([f.fires[1]], f.observed)


class HearthConfigTests(unittest.TestCase):
    def test_every_tunable_has_default_range_and_missing_key_guard(self):
        import json
        source = HEARTH.read_text()
        source += REGISTRY.read_text()
        dto = source.split('class HCHearthConfig', 1)[1].split('protected static', 1)[0]
        defaults = {key: (kind, json.loads(value)) for kind, key, value in re.findall(
            r'^    (int|float|bool) (\w+) = ([\d.]+|true|false);', dto, re.M)}
        registered = {key: (kind, float(value), float(low), float(high))
                      for key, kind, value, low, high in re.findall(
            r'HCAdd\("HearthFires\.(\w+)", "(\w+)", ([\d.]+), ([\d.]+), ([\d.]+), "HCHearthConfig"\)', source)}
        self.assertEqual(set(defaults), set(registered))
        self.assertTrue(defaults['Enabled'][1])
        for key, (kind, default) in defaults.items():
            rule_kind, value, low, high = registered[key]
            self.assertEqual(kind, rule_kind)
            self.assertEqual(default, value)
            self.assertLessEqual(low, default)
            self.assertLessEqual(default, high)
            self.assertIn('HCJsonFields.Has(text, "' + key + '")', source)
            if kind != 'bool':
                self.assertIn('HCOperatorSettingsRegistry.HCValid("HearthFires.' + key + '", decoded.' + key + ')', source)


if __name__ == '__main__':
    unittest.main()
