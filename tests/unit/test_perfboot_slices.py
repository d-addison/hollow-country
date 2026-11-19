"""Synthetic clocks/DTOs only; no DayZ performance evidence."""
import functools
import unittest
from types import SimpleNamespace as N
from tests.unit.test_hc_unit_budget import translated
from tests.unit.test_hc_perf_w45 import ROOT, WORLD, DEBUG
from tests.unit.test_group_server import EArray


class PerfBootSlices(unittest.TestCase):
    def test_raw_deadline_and_uncalibrated_start_are_bounded(self):
        source = (WORLD / 'HCPerfSlices.c').read_text().split('class HCPerfBootBudget', 1)[-1]
        clock = [100]
        env = dict(TickCount=lambda start: clock[0] - start)
        work = N(m_ClockSeeded=False, m_PreviousTick=0, m_TicksPerMs=0,
                 m_RawStart=0, m_RawDeadline=0, m_Limit=0, m_Used=0)
        for name in ('HCFrame', 'HCReset', 'HCContinue'):
            setattr(work, name, functools.partial(translated(source, name, env, 'HCPerfBootBudget'), work))
        work.HCFrame(1)
        work.HCReset(100000, 25)
        self.assertTrue(work.HCContinue())
        self.assertFalse(work.HCContinue(), 'only one atomic unit before calibration')
        clock[0] += 10000000  # explicit synthetic 10000 ticks/ms
        work.HCFrame(1)
        work.HCReset(100000, 25)
        for _ in range(25):
            self.assertTrue(work.HCContinue())
            clock[0] += 10000
        self.assertFalse(work.HCContinue())

    def test_many_leaves_progress_in_one_tick_and_stop_discards_cursor(self):
        source = (ROOT / 'mods/HollowCountry/scripts/4_World/Interiors/HCPerfInteriorSlices.c').read_text()
        source = source.replace('super.OnTick(deltaTime)', 'self.LegacyTick(deltaTime)')
        source = source.replace('super.OnStop()', 'self.LegacyStop()')
        source = source.replace('IsEnabled(settings)', 'self.IsEnabled(settings)')
        source = source.replace('HCSettings settings', 'HCEventSettings settings')
        source = source.replace('HCPerfConfig config', 'HCEventConfig config')
        clock, stage, decoded, reset = [1], [0], [], []
        budget = N()
        def begin(limit, ms): budget.deadline = clock[0] + ms
        budget.HCReset = begin
        budget.HCFrame = lambda dt: None
        budget.HCContinue = lambda: clock[0] < budget.deadline
        def prepare(work):
            if stage[0] >= 3: return 0
            clock[0] += 1
            stage[0] += 1
            return 0 if stage[0] % 3 == 0 else 1
        def legacy(dt):
            decoded.append(1)
            clock[0] += 1
            if len(decoded) >= 183: owner.m_PackLoading = False
        timer = N(HCAdd=lambda *a: None, HCItem=lambda *a: None, HCEndTick=lambda *a: None)
        owner = N(m_PackLoading=True, m_SlicedPack=True, m_PrepareBudget=budget,
                  m_PackSteps=timer, m_PrepareStep=0, m_LoadStep=1, IsEnabled=lambda s:True,
                  LegacyTick=legacy, LegacyStop=lambda: setattr(owner, 'm_PackLoading', False))
        env = dict(TickCount=lambda start:clock[0]-start, GetGame=lambda:N(IsServer=lambda:True),
                   HCServer=N(Get=lambda:N(GetSettings=lambda:N())),
                   HCPerfPlayers=N(HCGet=lambda:EArray()),
                   HCPerfConfig=N(HCGet=lambda:N(InteriorPackOnlineMs=25, InteriorPackEmptyMs=150, InteriorPackUnitsPerTick=4096)),
                   HCPerfBootBudget=lambda:budget,
                   HCW64InteriorLoad=N(HCPrepare=prepare, HCConsumed=lambda:stage.__setitem__(0, 0),
                                       HCReset=lambda:reset.append(True)))
        tick = translated(source, 'OnTick', env, 'HCInteriorsModule')
        config = env['HCPerfConfig'].HCGet()
        env['HCPerfConfig'].HCGet = lambda:config
        for deadline in (3, 25, 150):
            config.InteriorPackEmptyMs = deadline
            owner.m_PackLoading = True
            decoded.clear()
            stage[0] = 0
            for ticks in range(400):
                start = clock[0]
                tick(owner, 1)
                self.assertLessEqual(clock[0]-start, deadline)
                if not owner.m_PackLoading: break
            self.assertFalse(owner.m_PackLoading)
            if deadline == 150: self.assertLess(ticks+1, 10)
        owner.m_PackLoading = True
        translated(source, 'OnStop', env, 'HCInteriorsModule')(owner)
        self.assertFalse(owner.m_SlicedPack)
        self.assertEqual([True], reset)

    def test_snapshot_cadence_comes_from_config_and_off_is_cheap(self):
        source = (DEBUG / 'HCDebugSnapshotModule.c').read_text()
        source = source.replace('HCWorldTime()', 'self.HCWorldTime()').replace('new HCDebugSnapshot(worldTime)', 'MakeSnapshot(worldTime)')
        captures = []
        config = N(DebugSnapshotIntervalSeconds=300)
        env = dict(HCPerfConfig=N(HCGet=lambda:config),
                   MakeSnapshot=lambda time:captures.append(time) or N(HCCaptureNext=lambda:False))
        owner = N(m_Running=True, m_Elapsed=0, m_Save=None, m_Snapshot=None, m_SaveBudget=N(HCFrame=lambda dt:None), HCWorldTime=lambda:123)
        tick = translated(source, 'OnTick', env, 'HCDebugSnapshotModule')
        for _ in range(299): tick(owner, 1)
        self.assertEqual([], captures)
        tick(owner, 1)
        self.assertEqual([123], captures)
        owner.m_Running=False
        tick(owner, 1000)
        self.assertEqual([123], captures)

    def test_snapshot_encoder_yields_without_advancing_phase(self):
        source = (DEBUG / 'HCPerfSnapshotSave.c').read_text()
        owner = N(m_Phase=0, HCEncode=lambda phase:0)
        step = translated(source, 'HCStep', dict(STEP_MORE=1, STEP_DONE=0, STEP_FAILED=2), 'HCPerfSnapshotSave')
        self.assertEqual(1, step(owner))
        self.assertEqual(0, owner.m_Phase, 'a partially encoded layer must resume')

    def test_row_encoder_preserves_json_shape_and_escapes(self):
        import json
        from tests.unit.test_hc_operational_snapshot import NativeMap
        source = (DEBUG / 'HCPerfSnapshotSave.c').read_text()
        # Native out strings alone are adapted; all cursor/phase choices are authored.
        source = source.replace('HCDebugRoute route', 'HCEventRoute route')
        source = source.replace('HCDebugLayerStat stat', 'HCEventStat stat')
        source = source.replace('HCDebugPoint point', 'HCEventPoint point')
        import re
        source = re.sub(r'if \(!JsonFileLoader<[^>]+>\.MakeData\((\w+), encoded, error, false\)\) \{ return -1; \}',
                        r'encoded = NativeEncode(\1);', source)
        point = N(id='p"\\', x=1.5, z=2.5, label='synthetic', detail='line\nnext')
        route = N(layer='a"', id='r', label='route', points=[[1,2], [3,4]])
        stat = N(layer='a"', total=1, shown=1, truncated=0, unplaced=0)
        data = N(time=123, layers=NativeMap({'a"':EArray([point]), 'empty':EArray()}),
                 routes=EArray([route]), layerStats=EArray([stat]), operational=EArray(['state"\\']),
                 contributors=2, truncated=0, operationalTruncated=0)
        obj = N(m_Data=data, m_Row=0, m_Layer=0, m_LayerOpen=False, m_Phase=0, m_Layers='', m_Routes='', m_Operational='',
                m_Stats='', m_Text='', m_Bytes=0, m_Limit=1048576)
        native_calls = []
        def encode(value):
            native_calls.append(value)
            return json.dumps(value, default=lambda value:vars(value), separators=(',', ':'))
        env = dict(NativeEncode=encode, STEP_MORE=1, STEP_DONE=0, STEP_FAILED=2)
        for method in ('HCStep', 'HCEncode', 'HCEncodeLayer', 'HCAssemble'):
            setattr(obj, method, functools.partial(translated(source, method, env, 'HCPerfSnapshotSave'), obj))
        while obj.m_Phase < 4:
            before = len(native_calls)
            self.assertEqual(1, obj.HCStep())
            self.assertLessEqual(len(native_calls)-before, 1, 'whole collection serialized in one unit')
        actual = json.loads(obj.m_Text)
        self.assertEqual(vars(point), actual['layers']['a"'][0])
        self.assertEqual([], actual['layers']['empty'])
        self.assertEqual([vars(route)], actual['routes'])
        self.assertEqual([vars(stat)], actual['layerStats'])
        self.assertEqual(['state"\\'], actual['operational'])

    def test_registry_integration_fixture_and_missing_key_defaults(self):
        from tools.validate import settings_consistency as settings
        import json
        import re
        # Explicit fixture copy: this worker does not own HCPerfSettingsRegistry.c.
        # The exact required integration is retained in the final handoff.
        rows = settings.load_registry(include_scoped=True)
        perf = [r for r in rows if r['key'].startswith('Performance.')]
        fixture_registry = settings.PERF_REGISTRY.read_text()
        existing = set(re.findall(r'HCAdd\("([^\"]+)"', fixture_registry))
        additions = [r for r in perf if r['key'] not in existing]
        fixture_registry = fixture_registry.replace('    }\n}', settings.render_native_registry(additions)+'\n    }\n}')
        self.assertEqual([], settings.check_consistency(perf_registry=fixture_registry))
        source = (WORLD / 'HCPerfSlices.c').read_text()
        defaults = {k:json.loads(v) for k,v in re.findall(r'^    (?:int|bool) (\w+) = (\w+);',source,re.M)}
        bounds = {r['key'].split('.')[-1]:(r['min'], r['max']) for r in perf}
        env = dict(HCJsonFields=N(Has=lambda text,key:key in json.loads(text)),
                   HCOperatorSettingsRegistry=N(HCValid=lambda key,val: bounds[key.split('.')[-1]][0] <= val <= bounds[key.split('.')[-1]][1]))
        for key in defaults:
            source = re.sub(r'(?<![\w.])'+key+r' = decoded\.', 'self.'+key+' = decoded.', source)
        apply = translated(source, 'HCApply', env, 'HCPerfConfig')
        obj, zero = N(**defaults), N(**dict.fromkeys(defaults, 0))
        apply(obj, zero, '{}')
        self.assertEqual(defaults, vars(obj))
        apply(obj, zero, '{"InteriorPackOnlineMs":0,"DebugSnapshotIntervalSeconds":0}')
        self.assertEqual(25, obj.InteriorPackOnlineMs)
        self.assertEqual(300, obj.DebugSnapshotIntervalSeconds)

    def test_snapshot_save_stops_at_deadline_and_retains_job(self):
        source = (WORLD / 'HCPerfSlices.c').read_text().split('class HCPerfBootBudget', 1)[-1]
        clock = [1]
        work = N(m_ClockSeeded=True, m_PreviousTick=1, m_TicksPerMs=10000,
                 m_RawStart=0, m_RawDeadline=0, m_Limit=0, m_Used=0)
        env = dict(TickCount=lambda start:clock[0]-start)
        for name in ('HCFrame', 'HCReset', 'HCContinue'):
            setattr(work, name, functools.partial(translated(source, name, env, 'HCPerfBootBudget'), work))
        clock[0] += 10000000
        calls = []
        def step():
            clock[0] += 10000  # synthetic 1ms JSON row
            calls.append(1)
            return 1
        job = N(HCStep=step)
        owner = N(m_Running=True, m_Elapsed=0, m_Save=job, m_SaveBudget=work)
        env.update(HCPerfConfig=N(HCGet=lambda:N(SliceMs=4)),
                   HCDebugSnapshot=N(MAX_CONTRIBUTOR_POINTS=64),
                   HCSaveJob=N(STEP_FAILED=2, STEP_DONE=0))
        tick = translated((DEBUG / 'HCDebugSnapshotModule.c').read_text(), 'OnTick', env, 'HCDebugSnapshotModule')
        tick(owner, 1)
        self.assertEqual(4, len(calls))
        self.assertIs(job, owner.m_Save)
