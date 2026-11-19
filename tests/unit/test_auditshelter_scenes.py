"""Regional exterior scene policy; synthetic engine seams are not DayZ evidence."""
import copy
import json
from pathlib import Path
from types import SimpleNamespace as N
import unittest

from tests.unit.test_event_runtime import translate
from tests.unit.test_core_lifecycle import NativeArray

class SceneArray(NativeArray):
    def Get(self, index):
        return self[index]


ROOT = Path(__file__).resolve().parents[2]
MODULE = ROOT / 'mods/HollowCountry/scripts/4_World/Travel/HCShelterModule.c'
CATALOG = ROOT / 'mods/HollowCountry/scripts/4_World/Travel/HCShelterCatalog.c'
DATA = ROOT / 'mission/hollow-country/travel/auditshelter_scenes.json'


class RegionalScenes(unittest.TestCase):
    def test_tick_defers_observed_site_and_consumes_one_budgeted_scene(self):
        source = MODULE.read_text().replace("HCShelterRegionalConfig ", "HCEventConfig ").replace("HCShelterEntry ", "HCEventEntry ").replace("HCUnitBudget shared", "HCEventBudget shared")
        self.assertIn('void HCRegionalTick()', source, 'regional scenes have no bounded placement consumer')
        attempts, charges = [], []
        scene = N(Enabled=True)
        entry = N(Scene=scene, Attempted=False, Position=[1, 2, 3])
        visible = [True]
        budget = N(HCTakeFor=lambda consumer, cost: charges.append((consumer, cost)) or True)
        config = N(Enabled=True, WorkUnits=24, ObserverDistance=1100, BoundsToleranceSquared=.04)
        env = dict(HCShelterCatalog=N(HCRegionalConfig=lambda: config, Count=lambda: 1, Get=lambda i: entry),
                   HCServer=N(HCTickWork=lambda: budget), HCUnitBudget=N(HC_WORK_INTERIORS=1, HC_WORK_SHELTER=21),
                   HCObserverTransitionGate=N(CanTransition=lambda *args: not visible[0]))
        owner = type('SyntheticShelters', (), {})
        owner.HCRegionalTick = translate(source, 'HCRegionalTick', env, 'HCShelterModule', True)
        state = owner()
        state.m_RegionalCursor = 0
        state.HCPlaceRegional = attempts.append
        state.HCRegionalTick()
        self.assertEqual([], attempts, 'observer veto must precede world changes')
        visible[0] = False
        state.HCRegionalTick()
        self.assertEqual([entry], attempts)
        self.assertTrue(entry.Attempted)
        state.HCRegionalTick()
        self.assertEqual([entry], attempts, 'no recurring failed-scene retry loop')
        entry.Attempted = False
        config.Enabled = False
        state.HCRegionalTick()
        self.assertEqual([entry], attempts, 'operator opt-out is a cheap no-op')
        self.assertTrue(all(cost == 24 for _, cost in charges))

    def test_real_budget_advances_all_scenes_after_interiors_spends_twelve_units(self):
        from tests.unit.tick_budget_fixture import new_budget, budget_class
        budget, klass = new_budget(), budget_class()
        # Exact lead-owned constant; Core remains outside this worker's scope.
        klass.HC_WORK_SHELTER = 21
        klass.HC_WORK_CONSUMERS = 22
        entries = [N(Scene=N(Enabled=True), Attempted=False, Position=[i, 0, 0]) for i in range(5)]
        config = N(Enabled=True, WorkUnits=24, ObserverDistance=1100, BoundsToleranceSquared=.04)
        env = dict(HCShelterCatalog=N(HCRegionalConfig=lambda: config, Count=lambda: len(entries), Get=entries.__getitem__),
                   HCServer=N(HCTickWork=lambda: budget), HCUnitBudget=klass,
                   HCObserverTransitionGate=N(CanTransition=lambda *args: True))
        source = MODULE.read_text().replace('HCShelterRegionalConfig ', 'HCEventConfig ').replace('HCShelterEntry ', 'HCEventEntry ').replace('HCUnitBudget shared', 'HCEventBudget shared')
        owner = type('SyntheticBudgetShelters', (), {})
        owner.HCRegionalTick = translate(source, 'HCRegionalTick', env, 'HCShelterModule', True)
        state = owner()
        state.m_RegionalCursor = 0
        placed = []
        state.HCPlaceRegional = placed.append
        for tick in range(10):
            budget.HCReset(32)
            for visit in range(12):
                self.assertTrue(budget.HCTakeFor(klass.HC_WORK_INTERIORS, 1))
            state.HCRegionalTick()
            if tick < 5:
                self.assertEqual(tick + 1, len(placed), 'Interiors must not starve shelter placement')
                self.assertEqual(36, budget.HCUsed())
                self.assertEqual(1, budget.HCStarved())
        self.assertEqual(entries, placed)

    def test_config_validation_rejects_missing_limits_and_access_overlap(self):
        source = CATALOG.read_text().replace('HCShelterRegionalScene ', 'HCEventScene ').replace('HCShelterRegionalConfig ', 'HCEventConfig ').replace('HCShelterSurvey ', 'HCEventSurvey ').replace('array<float> slot :', 'HCEventPoint slot :')
        config = json.loads(DATA.read_text())
        def dto(value):
            if isinstance(value, dict):
                return N(**{k: dto(v) for k, v in value.items()})
            if isinstance(value, list):
                return NativeArray(dto(v) for v in value)
            return value
        config = dto(config)
        box = lambda lo, hi: bool(lo and hi and len(lo) == len(hi) == 3 and all(-512 <= a < b <= 512 for a, b in zip(lo, hi)))
        catalog = N(CandidateCount=lambda: 5, GetCandidate=lambda i: config.Scenes[i])
        env = dict(HCShelterCatalog=catalog, HCInteriorTemplates=N(BoxValid=box, AsVector=lambda p: p),
                   HCObserverTransitionGate=N(Finite=lambda v: v == v and abs(v) != float('inf')),
                   HCInteriorRules=N(SaneVector=lambda v, limit: all(abs(x) <= limit for x in v)))
        catalog.HCRegionalBox = translate(source, 'HCRegionalBox', env, 'HCShelterCatalog')
        valid = translate(source, 'HCRegionalValid', env, 'HCShelterCatalog')
        self.assertTrue(valid(config))
        for field in ('ObserverDistance', 'WorkUnits', 'BoundsToleranceSquared', 'SchemaVersion'):
            bad = copy.deepcopy(config)
            setattr(bad, field, 0)  # Explicit synthetic JsonFileLoader missing-field shape.
            self.assertFalse(valid(bad), field)
        bad = copy.deepcopy(config)
        bad.Scenes[0].Slots[0][0] = 0
        self.assertFalse(valid(bad), 'a prop must never enter the reserved roof/access envelope')
        bad = copy.deepcopy(config)
        bad.Scenes[0].ClipMin = None
        self.assertFalse(valid(bad))
        self.assertIn('HCJsonFields.Every(content, "Enabled", 3)', source)

    def test_real_batch_rollback_and_complete_only_publication(self):
        source = MODULE.read_text().replace('protected Object ', 'protected HCEventHandle ')
        for old, new in (('HCShelterRegionalScene ', 'HCEventScene '),
                         ('HCInteriorFurnishRow ', 'HCEventBinding '),
                         ('HCInteriorTemplateRoom ', 'HCEventRoom '),
                         ('HCInteriorTemplate ', 'HCEventTemplate ')):
            source = source.replace(old, new)
        created, deleted, updated, logs = [], [], [], []
        scene = N(Enabled=True, Id='synthetic', BuildingClass='SyntheticRoof', Position=[100, 0, 100],
                  ClipMin=[-3, -3, -2], ClipMax=[3, 3, 2], YardMin=[-10, -20, -6],
                  YardMax=[-6, 20, 6], AccessMin=[-5, -20, -4], AccessMax=[5, 20, 4])
        house = N(ClippingInfo=lambda target: target.__setitem__(slice(None), [scene.ClipMin, scene.ClipMax]))
        env = dict(EArray=SceneArray, str=str, Print=logs.append,
                   HCShelterCatalog=N(HCRegionalConfig=lambda: N(BoundsToleranceSquared=.04)),
                   HCInteriorFurnishRow=N, HCInteriorTemplateRoom=N,
                   HCInteriorTemplate=lambda: N(Rooms=NativeArray()),
                   HCInteriorTemplatePlacement=N(Resolve=lambda binding: house),
                   HCInteriorTemplates=N(AsVector=lambda value: value),
                   vector=N(DistanceSq=lambda a, b: sum((x-y)**2 for x, y in zip(a, b))),
                   GetGame=lambda: N(UpdatePathgraphRegionByObject=updated.append))
        # Only native fixed-size vector declaration syntax is adapted here.
        source = source.replace('vector regionalClip[2]', 'HCEventClip regionalClip')
        env['HCEventClip'] = lambda: [None, None]
        source = source.replace('HCEventClip regionalClip;', 'array<Object> regionalClip = new array<Object>();')
        owner = type('SyntheticRegionalOwner', (), {})
        for method in ('HCPlaceRegional', 'HCPlaceBatch', 'HCRegionalRefuse'):
            setattr(owner, method, translate(source, method, env, 'HCShelterModule', True))
        state = owner()
        state.m_Objects = NativeArray()
        state.m_Placed = state.m_RegionalFailed = 0
        state.m_RegionalReason = state.m_RefusalReason = ''
        state.Keepout = lambda *args: None
        state.DeleteProp = deleted.append
        fail_at = [2]
        def place(house, layout, prop, z):
            if len(created) == fail_at[0]:
                state.m_RefusalReason = 'synthetic_collision'
                return None
            handle = N(prop=prop)
            created.append(handle)
            return handle
        state.PlaceProp = place
        entry = N(Scene=scene, Position=scene.Position, Attempted=True, Placed=False, PlacementAnchor=None)
        state.HCPlaceRegional(entry)
        self.assertFalse(entry.Placed)
        self.assertEqual(created, deleted)
        self.assertEqual([], state.m_Objects)
        self.assertEqual([], updated)
        self.assertIsNone(state.m_RegionalScene)
        self.assertEqual(1, state.m_RegionalFailed, 'real collision remains a permanent failure')
        for veto_at in range(3):
            created.clear()
            deleted.clear()
            entry.Attempted = True
            fail_at[0] = veto_at
            def observed_place(house, layout, prop, z):
                if len(created) == fail_at[0]:
                    state.m_RefusalReason = 'observed_regional_prop'
                    return None
                handle = N(prop=prop)
                created.append(handle)
                return handle
            state.PlaceProp = observed_place
            state.HCPlaceRegional(entry)
            self.assertFalse(entry.Attempted, 'temporary prop observer veto must allow retry')
            self.assertFalse(entry.Placed)
            self.assertIsNone(entry.PlacementAnchor)
            self.assertEqual(created, deleted)
            self.assertEqual([], state.m_Objects)
            self.assertEqual([], updated)
            self.assertIsNone(state.m_RegionalScene)
            self.assertEqual(1, state.m_RegionalFailed, 'observer veto is not a permanent fault')
        # Observers leave: a later tick retries and publishes the complete batch.
        created.clear()
        state.PlaceProp = place
        fail_at[0] = -1
        config = N(Enabled=True, WorkUnits=24, ObserverDistance=1100, BoundsToleranceSquared=.04)
        env.update(HCShelterCatalog=N(HCRegionalConfig=lambda: config, Count=lambda: 1, Get=lambda i: entry),
                   HCServer=N(HCTickWork=lambda: N(HCTakeFor=lambda *args: True)),
                   HCUnitBudget=N(HC_WORK_INTERIORS=1, HC_WORK_SHELTER=21),
                   HCObserverTransitionGate=N(CanTransition=lambda *args: True))
        tick_source = MODULE.read_text().replace('HCShelterRegionalConfig ', 'HCEventConfig ').replace('HCShelterEntry ', 'HCEventEntry ').replace('HCUnitBudget shared', 'HCEventBudget shared')
        owner.HCRegionalTick = translate(tick_source, 'HCRegionalTick', env, 'HCShelterModule', True)
        state.m_RegionalCursor = 0
        state.HCRegionalTick()
        self.assertTrue(entry.Attempted)
        self.assertTrue(entry.Placed)
        self.assertIs(entry.PlacementAnchor, created[0])
        self.assertEqual(3, state.m_Objects.Count())
        self.assertEqual(created, updated)
        self.assertIn('regional_placed=synthetic props=3 runtime=PENDING', logs[-1])

    def test_five_exact_stock_scenes_reserve_roof_and_all_approaches(self):
        self.assertTrue(DATA.is_file(), 'regional scene/access data missing')
        data = json.loads(DATA.read_text())
        survey = json.loads((DATA.parent / 'route-surveys.json').read_text())
        self.assertTrue(data['Enabled'])
        self.assertEqual(5, len(data['Scenes']))
        candidates = {r['id']: r for r in survey['regional_candidates']}
        for scene in data['Scenes']:
            row = candidates[scene['Id']]
            self.assertEqual(row['position'], scene['Position'])
            self.assertEqual(row['building_class'], scene['BuildingClass'])
            self.assertEqual('pending', scene['RuntimeAcceptance'])
            self.assertTrue(scene['Enabled'])
            self.assertEqual(3, len(scene['Slots']))
            # Every full 1.2m maximum prop footprint lies west of the WHOLE
            # clipping box plus an authored walk-around lane, in model space.
            for slot in scene['Slots']:
                self.assertLess(slot[0] + 1.2, scene['AccessMin'][0])
                self.assertTrue(all(lo <= p - pad and p + pad <= hi for lo, p, hi, pad in
                                    zip(scene['YardMin'], slot, scene['YardMax'], (1.2, 2, 1.2))))
            self.assertLessEqual(scene['AccessMin'][0], scene['ClipMin'][0] - 2)
            self.assertGreaterEqual(scene['AccessMax'][2], scene['ClipMax'][2] + 2)
            self.assertEqual(0, scene['StockGrants'])
            self.assertFalse(scene['Evidence']['sample_is_candidate'])
            self.assertEqual(0, scene['Evidence']['path_tests'])

    def test_discovery_is_published_only_after_complete_batch(self):
        source = MODULE.read_text()
        self.assertIn('void HCPlaceRegional(HCShelterEntry entry)', source)
        method = source.split('void HCPlaceRegional(HCShelterEntry entry)', 1)[1].split('protected ', 1)[0]
        self.assertLess(method.index('if (!HCPlaceBatch'), method.index('entry.Placed = true'))
        self.assertIn('entry.PlacementAnchor = batch.Get(0)', method)
        self.assertIn('HCInteriorTemplatePlacement.Resolve', method)
        self.assertIn('HCRegionalValid', CATALOG.read_text())


if __name__ == '__main__':
    unittest.main()
