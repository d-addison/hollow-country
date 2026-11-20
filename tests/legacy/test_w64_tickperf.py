"""Explicit synthetic clocks/JSON; no DayZ timing or runtime acceptance evidence."""
import functools
import json
import re
import unittest
from pathlib import Path
from types import SimpleNamespace as N
from tests.legacy.test_group_server import EArray
from tests.legacy.test_hc_unit_budget import translated

ROOT = Path(__file__).resolve().parents[2]
INTERIORS = ROOT / 'mods/HollowCountry/scripts/4_World/Interiors'
WORLD = ROOT / 'mods/HollowCountry/scripts/4_World/World'


class NativeText(str):
    def Get(self, index): return NativeText(self[index])
    def __getitem__(self, key): return NativeText(super().__getitem__(key))
    def Substring(self, start, count): return NativeText(self[start:start + count])
    def Split(self, separator, out): out.extend(NativeText(v) for v in self.split(separator) if v)


def parser_fixture(content, schema):
    from tests.legacy.test_interior_templates_runtime import authored, Array
    strict = authored()
    source = (INTERIORS / 'HCW64InteriorStrict.c').read_text()
    for cls in ('HCW64InteriorFrame', 'HCInteriorTemplateCursor'):
        source = source.replace(cls, 'HCEvent' + cls)
    def frame():
        return N(Schema='', Phase=0, Count=0, List=False, Required=Array(), Seen=Array())
    cursor = lambda: N(Content='', Index=0, Nodes=0, Failed=False, CopyFrom=0, NativeText='')
    ports = N(**{name: strict[name] for name in ('Space', 'Code', 'Take', 'Value', 'CopyText',
                'StringToken', 'ArrayCap', 'SourceName')})
    ports.Keys = lambda name: NativeText(strict['Keys'](name))
    ports.Child = lambda name, key: NativeText(strict['Child'](name, key))
    env = dict(HCEventHCW64InteriorFrame=frame, HCEventHCInteriorTemplateCursor=cursor,
               HCInteriorTemplatesStrict=ports)
    obj = N(m_Cursor=cursor(), m_Frames=Array(), m_Done=False, m_Failed=False, m_Result='')
    for name in ('HCStart', 'HCPush', 'HCFinishFrame', 'HCVisit', 'HCStep', 'HCResult'):
        setattr(obj, name, functools.partial(translated(source, name, dict(env), 'HCW64InteriorStrict'), obj))
    obj.HCStart(NativeText(content), NativeText(schema))
    return obj, strict


class TickPerf(unittest.TestCase):
    def test_cursor_calls_share_one_tick_slice_instead_of_resetting_per_slot(self):
        source = (INTERIORS / 'HCInteriorPlacementCursor.c').read_text()
        source = source.replace('HCInteriorFurnishRow', 'HCEventFurnishRow')
        calls = []
        budget = N(left=0)
        def reset(*args):
            budget.left = 1
        def take():
            budget.left -= 1
            return budget.left >= 0
        budget.HCReset = reset
        budget.HCContinue = take
        budget.HCDeferred = lambda *args: None
        row = N(Props=EArray([1, 2, 3]))
        owner = N(m_LastCost=1, m_Complete=False, m_Budget=budget, m_Current=row,
                  m_Slot=0, m_FromDeferred=False, m_HousePlaced=0, m_Next=1,
                  m_DeferredRemaining=0)
        env = dict(CHEAP_UNITS=1, SLOT_UNITS=8,
                   HCInteriorTemplates=N(Loaded=lambda: True, FurnishRows=lambda: EArray([row])),
                   HCPerfPlayers=N(HCGet=lambda: EArray()),
                   HCInteriorRules=N(PlacementAdmitted=lambda: True),
                   HCInteriorTemplatePlacement=N(PlayersNearRow=lambda *a: False,
                       HCPlaceRowSlice=lambda *a: calls.append(a[4]) or True))
        tick = translated(source, 'HCTick', env, 'HCInteriorPlacementCursor')
        if 'void HCBeginTick()' in source:
            translated(source, 'HCBeginTick', dict(HCPerfConfig=N(HCGet=lambda: N(InteriorStepsPerTick=1))), 'HCInteriorPlacementCursor')(owner)
        for _ in range(3):
            tick(owner, N(), N(), EArray())
        self.assertEqual([0], calls, 'one tick reset its slice per slot')

    def test_pack_parser_yields_and_matches_existing_strict_results(self):
        from tests.legacy.test_interior_templates_runtime import pack
        fixtures = []
        for name, value in pack().items():
            schema = 'template'
            for prefix, kind in (('index', 'index'), ('classes-', 'classes'),
                                 ('furnish-', 'furnish'), ('search-groups-', 'groups')):
                if name.startswith(prefix): schema = kind
            fixtures.append((json.dumps(value), schema))
        fixtures += [('{' + '"Id":"a",' * 2 + '"Usages":[]}', 'group'),
                     ('[1,2,]', '@integer'), ('[2147483648]', '@integer'),
                     ('{"File":"a","Sha256":"b"}', 'file'),
                     ('[1,2,3]', '@integer'), ('[true,false]', '@boolean'),
                     ('[]', '@text'), ('{"File":"a"}', 'file')]
        for text, schema in fixtures:
            with self.subTest(schema=schema, text=text[:60]):
                parser, strict = parser_fixture(text, schema)
                expected = strict['NativeText'](text, schema)
                result = 1
                ticks = 0
                while result == 1 and ticks < 10000:
                    remaining = [7]  # explicit synthetic cost: one unit per parser visit
                    def take():
                        remaining[0] -= 1
                        return remaining[0] >= 0
                    result = parser.HCStep(N(HCContinue=take))
                    self.assertGreaterEqual(remaining[0], -1)
                    ticks += 1
                self.assertNotEqual(1, result, 'retained parser did not finish')
                self.assertEqual(expected, parser.HCResult())
                self.assertEqual(0 if expected else 2, result)
                if len(text) > 100: self.assertGreater(ticks, 1)

    def test_holdout_tick_spreads_native_ports_and_visits_each_body_once(self):
        source = (WORLD / 'HCHoldouts.c').read_text()
        for cls in ('HCHoldoutRow', 'HCHoldoutBody', 'HCSearchHouses', 'HCWorldModule'):
            source = source.replace(cls, 'HCEvent' + cls[2:])
        source = source.replace('for (int bodyIndex = m_Bodies.Count() - 1; bodyIndex >= 0; bodyIndex--)',
                                'for bodyIndex in range(m_Bodies.Count() - 1, -1, -1):')
        costs = [0]
        calls = []
        def work(name):
            costs[0] += 3  # explicit synthetic cost per native stage/body probe
            calls.append(name)
            return N()
        ledger = N(Since=1, State='EMPTY', Id='synthetic-house', HousePos=(0, 0, 0), CacheRef='')
        row = N(Ledger=ledger, Cache=N(Phase=2, EntityRef=''), Published=True)
        bodies = EArray(N(HoldoutId=ledger.Id,
                         Body=N(IsAlive=lambda i=i: work('body-' + str(i)) or True))
                        for i in range(3))
        owner = N(m_Ready=True, m_Elapsed=10, m_State=N(TemplatePin='', Rows=EArray([row])),
                  m_CatalogDirty=False, m_CatalogWorked=False, m_TickPhase=0, m_Next=0,
                  m_CampUnits=N(HCReset=lambda n: None, HCTake=lambda n: True),
                  m_WorkBudget=N(HCReset=lambda n: None, HCContinue=lambda: True),
                  FillCatalog=lambda: None, Count=lambda: 1,
                  Structure=lambda index: work('structure'),
                  SaveChanged=lambda: True, HCStepCamp=lambda *args: work('camp'),
                  m_Caches=EArray([N(LinkCache=lambda cache: work('cache'))]), m_Bodies=bodies)
        env = dict(HCEventWorldModule=N(Get=lambda: N()),
                   HCInteriorTemplates=N(Loaded=lambda: True), HCWorldClock=N(UTC=lambda: 100),
                   HCObserverTransitionGate=N(CanTransition=lambda *a: False), Structure=owner.Structure)
        tick = translated(source, 'OnTick', env, 'HCHoldouts')
        for _ in range(30):
            costs[0] = 0
            tick(owner, 1.)
            self.assertLessEqual(costs[0], 4, 'one tick ran several costly native stages')
            if owner.m_TickPhase == 0: break
        else: self.fail('row continuation never completed')
        self.assertEqual(['structure', 'cache', 'camp', 'body-2', 'body-1', 'body-0'], calls)
        self.assertEqual(1, owner.m_Next)

    def test_production_pack_adapter_reads_each_leaf_once_across_yields(self):
        self.run_pack_adapter(False)
        self.run_pack_adapter(True)

    def run_pack_adapter(self, paged):
        from tests.legacy.test_interior_templates_runtime import fixture, pack
        values = pack()
        if paged:
            index = values['index.json']
            lists = ('ClassFiles', 'TemplateFiles', 'FurnishFiles', 'GroupFiles')
            page = dict(SchemaVersion=3, Chunk=0,
                        SourcePins=[dict(Name=k, Sha256=v) for k, v in index['Sources'].items()],
                        **{key: index[key] for key in lists})
            root = {key: value for key, value in index.items() if key not in ('Sources', *lists)}
            root.update(SchemaVersion=3, IndexFiles=[dict(File='index-000.json', Sha256='a' * 64)])
            values['index.json'] = root
            values['index-000.json'] = page
        env = fixture(values=values, staged=True)[0]
        env['EnsureLoaded'](None)
        class Budget:
            def HCReset(self, limit, *args): self.left = limit
            def HCContinue(self):
                self.left -= 1
                return self.left >= 0
        budget = Budget()
        tokens = Budget()
        source = (INTERIORS / 'HCW64InteriorStrict.c').read_text()
        source = source[source.index('class HCW64InteriorLoad'):source.index('// At most one leaf/transition')]
        for field in ('s_Parser', 's_File', 's_Tokens'):
            source = source.replace(field, 'm_' + field[2:])
        source = source.replace('HCInteriorPackJob', 'HCEventPackJob')
        source = source.replace('new HCW64InteriorStrict', 'MakeParser()')
        api = N(HCNextLeaf=env['HCNextLeaf'], HCPackJob=env['HCPackJob'], Refuse=env['Refuse'],
                TEMPLATE_CHECKS_PER_STEP=7)
        def make_parser():
            parser = parser_fixture('[]', '@text')[0]
            start = parser.HCStart
            parser.HCStart = lambda raw, schema: start(NativeText(raw), NativeText(schema))
            return parser
        ports = dict(HCInteriorTemplates=api, HCInteriorPackIndex=env['HCInteriorPackIndex'],
                     HCPerfConfig=N(HCGet=lambda: N(SliceMs=4)),
                     MakeParser=make_parser)
        owner = N(m_Parser=None, m_File='', m_Tokens=tokens)
        for name in ('HCPrepare', 'HCConsumed', 'HCReset'):
            setattr(owner, name, functools.partial(translated(source, name, dict(ports),
                                                             'HCW64InteriorLoad'), owner))
        for iteration in range(2000):
            if iteration == 5:
                # Explicit process-stop model: discard only transient load state;
                # no partial pack has been published and the next start revalidates.
                self.assertFalse(env['Loaded']())
                env['HCLoadReset'](False)
                owner.HCReset()
                env['reads'].clear()
                env['EnsureLoaded'](None)
            budget.HCReset(1)
            prepared = owner.HCPrepare(budget)
            self.assertNotEqual(2, prepared)
            if prepared == 0:
                budget.HCReset(1)
                env['HCLoadStep'](None, budget)
                owner.HCConsumed()
            if env['HCLoadFinished'](): break
        else: self.fail('pack continuation never finished')
        self.assertTrue(env['Loaded'](), env['logs'])
        reads = env['reads']
        self.assertEqual(len(reads), len(set(reads)), 'a yielded leaf was re-read')
        self.assertEqual(1, len(env['s_Furnish']))


if __name__ == '__main__':
    unittest.main()
