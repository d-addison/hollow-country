"""Round 2 authored source tests. All engine/config ports are synthetic."""
import copy
import unittest
from types import SimpleNamespace as N
from tests.legacy import test_core_lifecycle as core
from tests.legacy import test_debug_map_layers as pins_tests
from tests.legacy.test_debug_map_layers import Recorder, SNAPSHOT, compile_authored, base_scope, CONSTANTS, EArray
from tools.validate import settings_consistency as settings


class SafeOff(unittest.TestCase):
    def test_shared_save_off_refuses_world_and_embedded_owners_before_start(self):
        events, receipts, baseline = [], [], []
        names = ('World', 'SettlementDecay', 'Escalation', 'Scenes', 'Ecology', 'Forage',
                 'Leads', 'Progression', 'Camps', 'InfectedLOD', 'WeatherDays', 'Holdouts')
        modules = [core.Module(name, events) for name in names]
        def status():
            result = N()
            result.HCPublish = lambda state, reason: vars(result).update(state=state, reason=reason)
            result.HCState = lambda: result.state
            result.HCReason = lambda: result.reason
            return result
        # Explicit synthetic embedded-service callbacks: these can run only if
        # their owning module's OnStart is admitted by the authored lifecycle.
        for module in modules:
            child = {'Camps': 'BuildingClaim', 'WeatherDays': 'VisualSeasons'}.get(module.name)
            if child:
                module.OnStart = lambda settings, name=module.name, child=child: events.extend(['start:' + name, 'embedded:' + child])
        for enabled in (False, True):
            events.clear(); receipts.clear(); baseline.clear()
            logs = []
            state, _ = core.fixture(modules, ports={
                'Print': logs.append,
                'HCPerfConfig': N(HCGet=lambda: N(EnableSharedSaves=enabled)),
                'HCOperationalStatus': status})
            state.m_Operational.HCCapture = lambda name, requested, report: receipts.append((name, requested, report))
            state.m_Changes.HCBaseline = baseline.append
            if not enabled:
                for module in modules[:-1]:
                    module.HCGetOperationalStatus = lambda: self.fail('unstarted owner status must not be called')
            else:
                for module in modules: module.HCGetOperationalStatus = lambda: None
            state.Start()
            expected = list(names) if enabled else ['Holdouts']
            self.assertEqual(expected, [m.GetName() for m in state.m_Active])
            self.assertEqual(['start:' + name for name in expected], [e for e in events if e.startswith('start:')])
            self.assertEqual(['embedded:BuildingClaim', 'embedded:VisualSeasons'] if enabled else [], [e for e in events if e.startswith('embedded:')])
            self.assertEqual(len(expected), len(baseline), 'late-readiness baselines follow active indices')
            if not enabled:
                for name, requested, report in receipts[:-1]:
                    self.assertIn('[HC ' + name + '] off reason=shared_save_service_operator_off', logs)
                    self.assertTrue(requested)
                    self.assertEqual(('refused', 'shared_save_service_operator_off'), (report.HCState(), report.HCReason()), name)
                state.Stop()
                self.assertEqual(['stop:Holdouts'], [e for e in events if e.startswith('stop:')])
                modules[0].HCGetOperationalStatus = lambda: None


class ScopedSettings(unittest.TestCase):
    def test_performance_scope_registered_and_mutations_detected(self):
        rows = settings.load_registry(include_scoped=True)
        perf = [r for r in rows if r['key'].startswith('Performance.')]
        self.assertEqual(10, len(perf))
        self.assertEqual([], settings.check_consistency())
        self.assertFalse(any(r['key'].startswith('Performance.') for r in settings.load_registry()),
                         'main settings validation must not accept profile-scoped keys')
        for key in ('Performance.SliceMs', 'Performance.EnableSharedSaves'):
            changed = [r for r in rows if r['key'] != key]
            self.assertTrue(settings.check_consistency(registry=changed), key)
        for field in ('default', 'max', 'owner'):
            changed = copy.deepcopy(rows)
            row = next(r for r in changed if r['key'] == 'Performance.SliceMs')
            row[field] = {'default': 3, 'max': 9, 'owner': 'Wrong'}[field]
            self.assertTrue(settings.check_consistency(registry=changed), field)
        dto = settings.PERF_NATIVE.read_text()
        registry = settings.PERF_REGISTRY.read_text()
        for source in (dto.replace('int SliceMs = 4;', 'int SliceMs = 3;'),
                       dto.replace('HCValid("Performance.SliceMs", decoded.SliceMs)', 'HCValid("Performance.HoldoutRowsPerTick", decoded.SliceMs)'),
                       dto.replace('Has(text, "EnableSharedSaves")', 'Has(text, "Wrong")'),
                       dto.replace('SliceMs = decoded.SliceMs;', 'SliceMs = decoded.HoldoutRowsPerTick;')):
            self.assertTrue(settings.check_consistency(perf_native=source))
        self.assertTrue(settings.check_consistency(perf_registry=registry.replace('4, 1, 10', '4, 1, 9')))


class PagedPins(unittest.TestCase):
    owner = pins_tests.GroupPinsLayer.owner
    place = pins_tests.GroupPinsLayer.place
    pin = pins_tests.GroupPinsLayer.pin
    def test_pages_count_true_total_despite_row_cap_and_touch_only_page(self):
        places = {g: [self.place('hc-ping:x:y') for _ in range(40)] for g in range(10, 15)}
        receiver, fn, calls = self.owner(groups=5, pin_sets=places)
        for cursor, expected in ((0, 80), (2, 80), (4, 40), (5, 0)):
            before = len(calls); rows = EArray()
            self.assertEqual(expected, fn(receiver, cursor, 2, 3, rows))
            self.assertLessEqual(len(calls) - before, 2)
            self.assertLessEqual(len(rows), 3)
        self.assertTrue(all(cap > 40 for cap in calls), 'display cap must not truncate counting')
        for cursor, group_cap, cap, output in ((-1, 1, 3, EArray()), (0, 0, 3, EArray()), (0, 1, 0, EArray()), (0, 1, 3, None)):
            before = len(calls)
            self.assertEqual(0, fn(receiver, cursor, group_cap, cap, output))
            self.assertEqual(before, len(calls))
        rows = EArray([self.pin() for _ in range(3)])
        self.assertEqual(40, fn(receiver, 0, 1, 3, rows))
        self.assertEqual(3, len(rows))

    def test_contributor_spreads_complete_sample_across_captures_and_resets_when_off(self):
        calls = []
        def page(cursor, group_cap, cap, rows):
            calls.append((cursor, group_cap, cap))
            rows.Insert(self.pin(i=cursor))
            return 40
        group = N(HCDebugPins=page, HCDebugPinGroupCount=lambda: 3)
        current = [group]
        scope = base_scope(HCGroupService=N(Get=lambda:current[0]), HCDebugSnapshot=N(**CONSTANTS), array=EArray,
                           HCDebugGroupPinRow=lambda:N())
        obj = N(m_Cursor=0, m_Total=0, m_Rows=EArray(), m_PublishedRows=EArray(), m_PublishedTotal=0, m_GroupOwner=None)
        fn = compile_authored(SNAPSHOT, 'HCDebugGroupPinsContributor', 'HCDescribe', scope, modded=False,
                              fields=tuple(vars(obj)))
        for capture in range(3):
            recorder = Recorder(); fn(obj, recorder)
            self.assertEqual(capture + 1, len(calls))
            if capture < 2: self.assertEqual([], recorder.notes)
        self.assertEqual([('group-pins', 120, 3)], recorder.notes)
        self.assertEqual([0, 1, 2], [c[0] for c in calls])
        current[0] = None
        recorder = Recorder(); fn(obj, recorder)
        self.assertEqual([], list(obj.m_PublishedRows))
        self.assertEqual([], recorder.notes)
