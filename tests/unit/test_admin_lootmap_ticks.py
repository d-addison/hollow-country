"""#191 loot map tick cap against the wall clock.

HCStep used to reset the shared HCWorkBudget (4 ms default deadline) BEFORE the native
cell query, so a query slower than the deadline spent a whole tick on the query and a
second tick on the rows: two ticks per cell against the one-per-cell the cap assumes.
The row loop now has its own named deadline (RowDeadlineMs) started AFTER the query.

The authored HCStep runs through the restricted statement adapter against the REAL
authored HCWorkBudget/HCUnitBudget and an explicit synthetic clock. Query and row costs
here are synthetic numbers, never a DayZ measurement.

RED: PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=.:tests/unit python3 -m unittest test_admin_lootmap_ticks -v
AssertionError: 4 != 8 (slow native query: 2 ticks per cell); worst case 12 != 16
"""
import math
from pathlib import Path
from types import SimpleNamespace as N
import unittest

from tests.unit.test_admin_lootmap import EStr, NativeArray, document
from tests.unit.test_admin_lootmap_wiring import authored_limits
from tests.unit.test_admin_test_kit import compile_authored, base_scope
from tests.unit.test_hc_infected_doors import shared_budget

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / 'mods/HollowCountry/scripts/4_World'
LOOT = SCRIPTS / 'Admin/HCAdminLootMap.c'
README = ROOT / 'tools/webmap/README.md'


class Harness:
    def __init__(self, rows_per_cell, query_seconds, row_seconds=0.0, world=1000):
        self.clock = [0.0]
        self.queries = 0
        self.limits = authored_limits()
        game = N(IsServer=lambda: True, GetTickTime=lambda: self.clock[0],
                 GetWorld=lambda: N(GetWorldSize=lambda: world), GetWorldName=lambda: EStr('chernarusplus'),
                 ConfigIsExisting=lambda name: False, GetObjectsAtPosition=self.query)
        self.rows_per_cell, self.query_seconds, self.row_seconds = rows_per_cell, query_seconds, row_seconds
        env = base_scope(GetGame=lambda: game, GetCEApi=lambda: object(), Vector=lambda x, y, z: (x, y, z),
                         HCGroupClock=N(Utc=lambda: 100), HCAdminLootDocument=document,
                         EntityAI=N(Cast=lambda entity: entity))
        env['Math'].Ceil = math.ceil
        env['Math'].Sqrt = math.sqrt
        static = N()
        env['HCAdminLootMap'] = static
        for name in ('HCValidFilter', 'HCJobTickCap', 'HCCellsAcross'):
            fn = compile_authored(LOOT, 'HCAdminLootMap', name, env, modded=False, native_strings=EStr)
            setattr(static, name, lambda *args, fn=fn: fn(static, *args))
        # The statement adapter floors '/'; the one float division goes through a true divide.
        static.HCCellsAcross = lambda size, cell: math.ceil(size / cell)
        self.static = static
        units = shared_budget(SCRIPTS / 'Core/HCUnitBudget.c', 'HCUnitBudget', {},
                              ('HCReset', 'HCTake', 'HCCharge', 'HCUsed'), game)
        work = shared_budget(SCRIPTS / 'World/HCWorkBudget.c', 'HCWorkBudget', dict(m_LogAfter=0.),
                             ('HCReset', 'HCMayContinue', 'HCContinue'), game)
        self.job = N(m_Limits=self.limits, m_Document=None, m_Candidates=NativeArray(), m_Cargos=NativeArray(),
                     m_Cursor=0, m_Cell=0, m_Across=0, m_Size=0, m_Loaded=False, m_MinX=0, m_MinZ=0,
                     m_MaxX=0, m_MaxZ=0, m_Ticks=0, m_MaxTicks=0, m_Budget=work, m_Units=units)
        names = ('HCStart', 'HCStep', 'HCQueryCell', 'HCObserve', 'HCFinish', 'HCMatches')
        for name in names:
            fn = compile_authored(LOOT, 'HCAdminLootMap', name, env, names, modded=False, native_strings=EStr,
                                  fields=('m_Document', 'm_Cursor', 'm_Cell', 'm_Ticks', 'm_MaxTicks'))
            setattr(self.job, name, lambda *args, fn=fn: fn(self.job, *args))

    def query(self, pos, radius, candidates, cargos):
        self.queries += 1
        self.clock[0] += self.query_seconds  # one native call cannot be preempted
        for _ in range(self.rows_per_cell):
            candidates.append(N(GetType=self.row))

    def row(self):
        self.clock[0] += self.row_seconds  # synthetic row cost, never a DayZ measurement
        return EStr('Other')

    def run(self):
        assert self.job.HCStart(EStr('Bandage'), 1000)
        ticks = 0
        while ticks < 500:
            ticks += 1
            self.clock[0] += 1.0  # the next core tick, 1000 ms later
            if self.job.HCStep():
                break
        return ticks


class TickCapAgainstWallClock(unittest.TestCase):
    CELLS = 4  # 1000 m world / 500 m sub-cells, explicit synthetic edge

    def test_slow_native_query_does_not_cost_a_second_tick_per_cell(self):
        # 20 ms query (5x the 4 ms row deadline), 3 cheap rows per cell.
        h = Harness(rows_per_cell=3, query_seconds=0.020)
        ticks = h.run()
        self.assertEqual('observed', h.job.m_Document.state)
        self.assertEqual((self.CELLS, 3 * self.CELLS), (h.queries, h.job.m_Document.scanned))
        self.assertEqual(self.CELLS, ticks)
        self.assertLessEqual(ticks, h.job.m_MaxTicks)

    def test_worst_case_rows_still_fit_the_cap_with_slow_queries(self):
        limits = authored_limits()
        # 600 rejected rows per cell: ceil(600 / 256) = 3 row ticks, the query shares the first.
        h = Harness(rows_per_cell=600, query_seconds=0.050)
        ticks = h.run()
        self.assertEqual('observed', h.job.m_Document.state)
        self.assertEqual(self.CELLS * math.ceil(600 / limits.MaxRowsPerStep), ticks)
        self.assertLessEqual(ticks, h.job.m_MaxTicks)

    def test_slow_row_loop_still_finishes_because_the_row_floor_is_deterministic(self):
        # Wave 12 (#193): every row costs 1 ms of synthetic clock, so the 4 ms wall-clock
        # deadline alone allowed only ~4 rows per tick: 600 rows x 4 cells = ~600 ticks
        # against a cap of ~357, ending in the job_tick_cap refusal.
        limits = authored_limits()
        h = Harness(rows_per_cell=600, query_seconds=0.0, row_seconds=0.001)
        ticks = h.run()
        self.assertEqual('observed', h.job.m_Document.state, h.job.m_Document.reason)
        self.assertEqual(self.CELLS * 600, h.job.m_Document.scanned)
        self.assertEqual(self.CELLS * math.ceil(600 / limits.MinRowUnitsPerTick), ticks)
        self.assertLessEqual(ticks, h.job.m_MaxTicks)

    def test_every_tick_spends_at_least_the_row_floor_before_the_deadline_may_stop_it(self):
        limits = authored_limits()
        h = Harness(rows_per_cell=600, query_seconds=0.0, row_seconds=0.001)
        h.clock[0] += 1.0
        assert h.job.HCStart(EStr('Bandage'), 1000)
        self.assertFalse(h.job.HCStep())
        self.assertEqual(limits.MinRowUnitsPerTick, h.job.m_Document.scanned)

    def test_row_deadline_remains_an_upper_bound_and_the_cap_is_sized_from_the_floor(self):
        limits = authored_limits()
        # The floor never exceeds the unit ceiling, so MaxRowsPerStep stays the hard cap.
        self.assertLessEqual(limits.MinRowUnitsPerTick, limits.MaxRowsPerStep)
        h = Harness(rows_per_cell=600, query_seconds=0.0, row_seconds=0.0)
        self.assertTrue(h.job.HCStart(EStr('Bandage'), 1000))
        units = limits.MaxItemsScanned + (limits.MatchRowUnits - 1) * limits.MaxMatches
        rows = math.ceil(units / limits.MinRowUnitsPerTick)
        rows += rows * limits.TickCapHeadroomPercent // 100
        self.assertEqual(self.CELLS + rows + 1, h.job.m_MaxTicks)
        self.assertIn('MinRowUnitsPerTick', README.read_text())
        self.assertIn('TickCapHeadroomPercent', README.read_text())

    def test_row_deadline_is_a_named_limit_and_the_readme_states_the_assumption(self):
        self.assertGreaterEqual(authored_limits().RowDeadlineMs, 1)
        text = README.read_text()
        self.assertIn('RowDeadlineMs', text)
        self.assertNotIn('Every tick ends at a sub-cell boundary or\nwith the row budget spent', text)


if __name__ == '__main__':
    unittest.main()
