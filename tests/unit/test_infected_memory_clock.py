"""Execute authored memory/admin reads with synthetic UTC, DTOs and native ports.

Issue #164 regression tests. No Enforce compilation or DayZ behavior is proved;
runtime acceptance remains pending.

2026-11-18 RED (before source edits):
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.unit.test_infected_memory_clock -v
Ran 6 tests; FAILED (failures=11). Admin list returned heat=0 instead of
heat=0.5, and small-skew Record failed assertTrue(f.api.Active()).
GREEN (21 tests, OK):
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.unit.test_infected_memory_clock tests.unit.test_group_null_context tests.unit.test_v1_combined_rpc -v
"""
from tests.unit.test_c1_infectedcfg import tuning_fixture
import copy
from datetime import datetime, timezone
import json
import re
from types import SimpleNamespace as N
import unittest

from tests.unit.test_admin_test_kit import ADMIN, compile_authored, real_math
from tests.unit.test_event_runtime import ROOT, translate
from tests.unit.test_group_clock import authored_clock, epoch
from tests.unit.test_group_server import EArray


class MemoryFixture:
    """Only syntax/native seams are adapted; clock and memory policy are authored."""
    def __init__(self, now=0):
        self.last = epoch(2026, 11, 16, 12)
        self.now = self.last + now
        self.logs = []
        fixture = self

        class NativeUTC:
            def date(self):
                d = datetime.fromtimestamp(fixture.now, timezone.utc)
                return d.year, d.month, d.day

            def time(self):
                d = datetime.fromtimestamp(fixture.now, timezone.utc)
                return d.hour, d.minute, d.second

        self.clock = authored_clock(NativeUTC())
        self.clock['s_LastUtc'] = self.last
        self.api = N()
        self.memory = N(m_Healthy=True, m_Dirty=False, m_LastUtc=self.last,
                        m_RecordUtc=self.last, m_RecordCount=0, m_LogUtc=self.last,
                        m_State=N(Version=1, CellMetres=500, WorldName='synthetic_world',
                                  SavedUtc=self.last, Cells=EArray([
                                      N(X=0, Z=0, Value=0.5, UpdatedUtc=self.last),
                                      N(X=1, Z=0, Value=0.7, UpdatedUtc=self.last)])))
        self.api.s_Instance = self.memory
        source = (ROOT / '4_World/Infected/HCInfectedMemory.c').read_text()
        for name, value in re.findall(r'static const int (\w+) = (\d+);', source):
            setattr(self.api, name, int(value))
        # Adapt type declarations, static fields, for loops and increments only.
        source = source.replace('HCInfectedMemoryCell', 'HCEventMemoryCell')
        source = re.sub(r'(?<![\w.])s_Instance\b', 'Memory.s_Instance', source)
        for name in vars(self.api):
            if name != 's_Instance':
                source = re.sub(r'(?<![\w.])' + name + r'\b', 'Memory.' + name, source)
        source = re.sub(r'for \(int (\w+) = ([^;]+); \1 < ([^;]+); \1\+\+\)',
                        r'foreach (int \1 : range(\2, \3))', source)
        source = re.sub(r'\b(\w+)\+\+;', r'\1 += 1;', source)
        self.scope = dict(HCInfectedTuning=tuning_fixture(), Memory=self.api, HCInfectedMemory=self.api,
                          HCGroupClock=N(**self.clock), Math=real_math(), Print=self.logs.append,
                          HCEventMemoryCell=lambda: N(X=-401, Z=-401, Value=0.0, UpdatedUtc=0),
                          HCInfectedStore=N(ValidPosition=lambda pos: True),
                          GetGame=lambda: N(IsServer=lambda: True))
        for name in ('Fail', 'Now', 'Find', 'Add'):
            fn = translate(source, name, self.scope, 'Memory', member=True)
            match = re.search(r'\b' + name + r'\(([^)]*)\)\s*\{', source)
            defaults = [json.loads(p.split('=', 1)[1].strip())
                        for p in match[1].split(',') if '=' in p]
            fn.__defaults__ = tuple(defaults)
            setattr(self.memory, name, fn.__get__(self.memory))
        for name in ('Active', 'Decayed', 'Heat', 'Record', 'CohortSizeAtHeat', 'ResponseLimitAtHeat'):
            setattr(self.api, name, translate(source, name, self.scope, 'Memory'))
        self.memory.Decayed = self.api.Decayed
        near_scope = dict(self.scope, s_Instance=self.memory)
        for name in ('Active', 'Heat', 'CohortSizeAtHeat', 'ResponseLimitAtHeat'):
            near_scope[name] = getattr(self.api, name)
        near = compile_authored(ADMIN / 'HCAdminDirectors.c', 'HCInfectedMemory',
                                'HCAdminNear', near_scope)
        self.api.HCAdminNear = lambda pos: near(None, pos)

    def snapshot(self):
        return (copy.deepcopy({k: v for k, v in vars(self.memory).items() if not callable(v)}),
                self.api.s_Instance is self.memory,
                self.clock['s_LastUtc'], list(self.logs))

    def admin_list(self):
        # Execute the actual list caller as well as HCAdminNear -> Heat -> Now.
        absent = N(Cast=lambda module: None)
        scope = dict(self.scope, HCInfectedModule=absent, HCDeadDrops=absent,
                     HCForageModule=absent, HCSettlementDecay=absent,
                     HCAdminModuleNamed=lambda name: None)
        nearby = compile_authored(ADMIN / 'HCAdminStatus.c', 'HCServer',
                                  'HCAdminNearby', scope)
        reply = N(Lines=EArray())
        nearby(None, reply, [10, 0, 10])
        return next(line for line in reply.Lines if 'list memory ' in line)


class InfectedMemoryClockTests(unittest.TestCase):
    def test_admin_list_with_future_samples_never_changes_memory_or_clock(self):
        for skew in (1, 300, 301, 86400):
            with self.subTest(skew=skew):
                f = MemoryFixture(-skew)
                before = f.snapshot()
                for _ in range(3):
                    self.assertIn('list memory heat=0.5', f.admin_list())
                    self.assertTrue(f.api.Active())
                    self.assertEqual(before, f.snapshot())

    def test_forward_heat_read_never_advances_any_watermark(self):
        f = MemoryFixture(60)
        before = f.snapshot()
        self.assertAlmostEqual(0.5 * (1 - 60 / 259200), f.api.Heat([10, 0, 10]))
        self.assertEqual(before, f.snapshot())

    def test_small_skew_record_preserves_samples_and_timestamp(self):
        for skew in (1, 299, 300):
            with self.subTest(skew=skew):
                f = MemoryFixture(-skew)
                other = copy.deepcopy(f.memory.m_State.Cells[1])
                f.api.Record([10, 0, 10], 1)
                self.assertTrue(f.api.Active())
                self.assertEqual(f.last, f.memory.m_LastUtc)
                self.assertEqual(f.last, f.memory.m_State.Cells[0].UpdatedUtc)
                self.assertAlmostEqual(0.85, f.memory.m_State.Cells[0].Value)
                self.assertEqual(other, f.memory.m_State.Cells[1])
                self.assertTrue(f.memory.m_Dirty)
                self.assertEqual([], f.logs)

    def test_small_skew_new_cell_and_record_cap_use_retained_second(self):
        f = MemoryFixture(-300)
        f.api.Record([1010, 0, 10], 1)
        self.assertTrue(f.api.Active())
        self.assertEqual(3, len(f.memory.m_State.Cells))
        self.assertAlmostEqual(0.35, f.memory.m_State.Cells[-1].Value)
        self.assertEqual(f.last, f.memory.m_State.Cells[-1].UpdatedUtc)
        f.memory.m_RecordCount = 32
        before = f.snapshot()
        f.api.Record([10, 0, 10], 1)
        self.assertEqual(before, f.snapshot())

    def test_large_skew_write_fails_once_and_preserves_samples(self):
        f = MemoryFixture(-301)
        cells = copy.deepcopy(f.memory.m_State.Cells)
        for _ in range(64):
            f.api.Record([10, 0, 10], 1)
        self.assertFalse(f.api.Active())
        self.assertEqual(cells, f.memory.m_State.Cells)
        self.assertEqual(f.last, f.memory.m_LastUtc)
        self.assertEqual(1, len(f.logs))
        self.assertIn('clock-skew', f.logs[0])

    def test_forward_write_resumes_decay_after_clock_catches_up(self):
        f = MemoryFixture(-1)
        f.api.Record([10, 0, 10], 1)
        self.assertTrue(f.api.Active())
        f.now = f.last + 60
        f.api.Record([10, 0, 10], 0.1)
        self.assertEqual(f.now, f.memory.m_LastUtc)
        self.assertEqual(f.now, f.memory.m_State.Cells[0].UpdatedUtc)
        self.assertAlmostEqual(0.85 * (1 - 60 / 259200) + 0.035,
                               f.memory.m_State.Cells[0].Value)


if __name__ == '__main__':
    unittest.main()
