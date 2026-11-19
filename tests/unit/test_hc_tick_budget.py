"""Wave 13 / issue #138: ONE shared per-tick work budget owned by HCServer.

Executes the AUTHORED HCUnitBudget.HCTakeFor / HCEndTick / HCWindowReport methods, the authored static
HCServer.HCTickWork accessor, the real HCServer.Tick, the real HCInteriorsModule lock-expiry loop and the real
HCInfectedModule actor sampling loop through the repo's syntax-only translators (tick_budget_fixture). Item
counts, order and cursors are SYNTHETIC offline evidence about the control flow; they say nothing about DayZ
timing or engine behaviour. runtime=PENDING until a native boot prints the '[HC TickWork] window=' line.

No-starvation rule (chosen): the first request of every consumer in a tick is admitted even when the budget is
spent ("forced item"), at most once per consumer per tick. Exact bound per tick:
    total <= MaxTickWorkItems + (HC_WORK_CONSUMERS - 1)
(the first request of the tick is admitted by the plain budget rule, so only the later consumers can be forced).

RED (2026-11-19, base 552ed93, this file copied onto the base tree):
  PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.unit.test_hc_tick_budget
  -> FAILED on the base tree: HCUnitBudget has no HCTakeFor and HCServer has no HCTickWork (the fixture
     and this file copied onto the base tree); see the commit message for the exact failing line.
GREEN: the same command on the wave 13 tree.
"""
import re
import unittest
from pathlib import Path
from types import SimpleNamespace as N

from tests.unit import test_core_lifecycle as core
from tests.unit import test_infected_admission as infected
from tests.unit import test_search_economy_integration as search
from tests.unit import test_v1_combined_flags as combined
from tests.unit import tick_budget_fixture as tickbudget
from tests.unit.test_group_server import EArray

SCRIPTS = Path(__file__).resolve().parents[2] / "mods/HollowCountry/scripts"
CONST = tickbudget.constants()
# .get: the base tree has no consumer ids, so the behavioural tests fail there instead of the import.
INFECTED, INTERIORS = CONST.get("HC_WORK_INFECTED", 0), CONST.get("HC_WORK_INTERIORS", 1)
CONSUMERS = CONST.get("HC_WORK_CONSUMERS", 5)


class BudgetRuleTests(unittest.TestCase):
    def test_consumer_ids_are_distinct_small_ints_and_unbounded_is_huge(self):
        ids = [CONST[name] for name in CONST if name.startswith("HC_WORK_") and name not in
               ("HC_WORK_CONSUMERS", "HC_WORK_UNBOUNDED")]
        self.assertEqual(len(ids), len(set(ids)))
        self.assertEqual(list(range(CONSUMERS)), sorted(ids))
        self.assertGreater(CONST["HC_WORK_UNBOUNDED"], 1000000)

    def test_a_spent_budget_still_admits_each_consumers_first_item_once(self):
        budget = tickbudget.new_budget()
        budget.HCReset(4)
        taken = [budget.HCTakeFor(INFECTED, 1) for _ in range(6)]
        self.assertEqual([True] * 4 + [False] * 2, taken)
        self.assertEqual(0, budget.HCStarved())
        # The budget is spent: another consumer gets exactly one forced unit.
        self.assertTrue(budget.HCTakeFor(INTERIORS, 1))
        self.assertFalse(budget.HCTakeFor(INTERIORS, 1))
        self.assertEqual(1, budget.HCStarved())
        self.assertEqual(5, budget.HCUsed())

    def test_exact_bound_is_limit_plus_one_forced_unit_per_later_consumer(self):
        for limit in (1, 4, 8, 32):
            with self.subTest(limit=limit):
                budget = tickbudget.new_budget()
                budget.HCReset(limit)
                total = 0
                for consumer in range(CONSUMERS):
                    while budget.HCTakeFor(consumer, 1):
                        total += 1
                self.assertEqual(limit + CONSUMERS - 1, total)
                self.assertEqual(CONSUMERS - 1, budget.HCStarved())

    def test_a_consumer_that_finds_budget_left_is_not_counted_as_starved(self):
        budget = tickbudget.new_budget()
        budget.HCReset(8)
        for _ in range(3):
            self.assertTrue(budget.HCTakeFor(INFECTED, 1))
        for _ in range(5):
            self.assertTrue(budget.HCTakeFor(INTERIORS, 1))
        self.assertEqual(0, budget.HCStarved())
        self.assertEqual(8, budget.HCUsed())

    def test_reset_clears_forced_flags_so_the_next_tick_forces_again(self):
        budget = tickbudget.new_budget()
        for tick in range(3):
            budget.HCReset(2)
            while budget.HCTakeFor(INFECTED, 1):
                pass
            self.assertTrue(budget.HCTakeFor(INTERIORS, 1), tick)
            self.assertFalse(budget.HCTakeFor(INTERIORS, 1), tick)
            self.assertEqual(1, budget.HCStarved(), tick)

    def test_window_report_has_the_perf_fields_once_per_window_and_stays_pending(self):
        budget = tickbudget.new_budget()
        lines = []
        for tick in range(130):
            budget.HCReset(4)
            while budget.HCTakeFor(INFECTED, 1):
                pass
            budget.HCTakeFor(INTERIORS, 1)
            if budget.HCEndTick(1.0, 60):
                lines.append(budget.HCWindowReport())
        self.assertEqual(2, len(lines), lines)
        self.assertIn("[HC TickWork] window=1 ticks=60 limit=4 shared_used_max=5 shared_starved=60", lines[0])
        self.assertIn("window=2", lines[1])
        self.assertTrue(all("runtime=PENDING" in line for line in lines))
        self.assertIn("shared_used_max=", budget.HCWindowFields())
        self.assertIn("shared_starved=", budget.HCWindowFields())


class AccessorTests(unittest.TestCase):
    def test_no_hcserver_instance_returns_a_usable_budget_that_never_refuses(self):
        klass = tickbudget.budget_class()
        accessor = tickbudget.tick_work_accessor(None, klass)
        budget = accessor()
        self.assertIsNotNone(budget)
        self.assertTrue(all(budget.HCTakeFor(INFECTED, 1) for _ in range(5000)))
        self.assertIs(budget, accessor(), "the idle budget is allocated once, not per call")
        self.assertTrue(budget.HCTakeFor(INTERIORS, 1))

    def test_an_instance_outside_a_core_tick_gets_the_idle_budget_not_the_spent_core_one(self):
        klass = tickbudget.budget_class()
        state = N(m_TickWork=tickbudget.new_budget(), m_TickActive=False)
        state.m_TickWork.HCReset(1)
        state.m_TickWork.HCTakeFor(INFECTED, 1)
        accessor = tickbudget.tick_work_accessor(state, klass)
        idle = accessor()
        self.assertIsNot(idle, state.m_TickWork)
        self.assertTrue(all(idle.HCTakeFor(INFECTED, 1) for _ in range(100)))

    def test_during_a_core_tick_the_accessor_returns_the_shared_budget(self):
        klass = tickbudget.budget_class()
        state = N(m_TickWork=tickbudget.new_budget(), m_TickActive=True)
        accessor = tickbudget.tick_work_accessor(state, klass)
        self.assertIs(state.m_TickWork, accessor())
        self.assertIs(state.m_TickWork, accessor())


class CoreTickTests(unittest.TestCase):
    def test_tick_resets_the_shared_budget_marks_it_active_only_inside_and_prints_once_per_window(self):
        f = combined.CoreFixture()
        f.state.Start()
        f.state.m_Settings.MaxTickWorkItems = 7
        seen = []
        klass = tickbudget.budget_class()
        accessor = tickbudget.tick_work_accessor(f.state, klass)

        def probe(elapsed):
            budget = accessor()
            seen.append((f.state.m_TickActive, budget is f.state.m_TickWork, budget.HCLimit(), budget.HCUsed()))
            budget.HCTakeFor(INFECTED, 1)
        f.modules["Infected"].OnTick = probe
        for _ in range(61):
            f.now += 1
            f.state.Tick()
        self.assertEqual([(True, True, 7, 0)] * 61, seen)
        self.assertFalse(f.state.m_TickActive)
        lines = [line for line in f.profile.logs if "[HC TickWork] window=" in line]
        self.assertEqual(1, len(lines), lines)
        self.assertIn("limit=7 shared_used_max=1 shared_starved=0; runtime=PENDING", lines[0])
        f.state.Stop()
        self.assertFalse(f.state.m_TickActive)


def site_class(visits):
    class Site:
        Deadline = 1000.

        def __init__(self, index):
            self.index = index

        @property
        def Owner(self):
            visits.append(("interior", self.index))
            return object()
    return Site


class Actor:
    def __init__(self, index):
        self.index = index


class TwoConsumerFixture:
    """Real HCServer.Tick driving the real Interiors lock loop and the real Infected sampling loop."""

    def __init__(self, limit, interiors_first, sites=12, actors=24):
        self.f = combined.CoreFixture()
        self.f.state.Start()
        self.f.state.m_Settings.MaxTickWorkItems = limit
        self.limit = limit
        self.visits = []
        klass = tickbudget.budget_class()
        accessor = tickbudget.tick_work_accessor(self.f.state, klass)
        self.infected = infected.StartedModule(flags=infected.NO_ADMISSION, hordes=False, work=limit)
        self.infected.tick_klass, self.infected.tick_work = klass, accessor
        self.infected.start()
        self.infected.ctx.m_Actors = infected.Array(Actor(i) for i in range(actors))
        self.infected.ctx.SampleActor = lambda actor: self.visits.append(("infected", actor.index))
        # Synthetic end of sweep: the real FinishSweep restarts the cursor; the sweep wraps to actor 0.
        self.infected.ctx.FinishSweep = lambda now: setattr(self.infected.ctx, "m_Cursor", 0)
        self.utc = 10001
        self.interior = search.SearchIntegrationTests()
        self.interior.setUp()
        tickbudget.install(self.interior.env, self.f.state, klass)
        Site = site_class(self.visits)
        self.interior.t.m_Sites = EArray(Site(i) for i in range(sites))
        self.interior.t.IsEnabled = lambda settings: settings.EnableInteriors
        self.f.modules["Infected"].OnTick = self.tick_infected
        self.f.modules["Interiors"].OnTick = lambda dt: self.interior.call("OnTick", dt)
        order = ["Interiors", "Infected"] if interiors_first else ["Infected", "Interiors"]
        rest = [m for m in self.f.state.m_Active if m.GetName() not in order]
        by_name = {m.GetName(): m for m in self.f.state.m_Active}
        self.f.state.m_Active[:] = [by_name[name] for name in order] + rest

    def tick_infected(self, dt):
        self.utc += 1
        self.infected.tick(self.utc)

    def run_tick(self):
        self.visits.clear()
        self.f.now += 1
        self.f.state.Tick()
        return list(self.visits)


class TwoConsumerStarvationTests(unittest.TestCase):
    def run_ticks(self, limit, interiors_first, ticks):
        fixture = TwoConsumerFixture(limit, interiors_first)
        per_tick = [fixture.run_tick() for _ in range(ticks)]
        return fixture, per_tick

    def assert_cursors(self, per_tick, sites=12, actors=24):
        interior = [i for tick in per_tick for kind, i in tick if kind == "interior"]
        sampled = [i for tick in per_tick for kind, i in tick if kind == "infected"]
        # Lock cursor: contiguous modulo the site count, so nothing is skipped or repeated within a lap.
        self.assertEqual([(interior[0] + n) % sites for n in range(len(interior))], interior)
        # Sampling cursor: strictly the next actor each time (wrapping at the sweep end); no repeats or gaps.
        self.assertEqual([n % actors for n in range(len(sampled))], sampled)

    def test_interiors_first_spends_the_budget_and_infected_still_progresses_every_tick(self):
        fixture, per_tick = self.run_ticks(8, True, 8)
        bound = 8 + CONSUMERS - 1
        for index, tick in enumerate(per_tick):
            kinds = [kind for kind, _ in tick]
            self.assertLessEqual(len(tick), bound, (index, tick))
            self.assertGreaterEqual(kinds.count("interior"), 1, (index, tick))
            self.assertGreaterEqual(kinds.count("infected"), 1, (index, tick))
            self.assertEqual(8 + 1, len(tick), "8 interior units, then the one forced infected unit")
        self.assert_cursors(per_tick)
        sampled = [i for tick in per_tick for kind, i in tick if kind == "infected"]
        self.assertEqual(8, len(sampled), "one forced infected unit per tick")

    def test_infected_first_spends_its_cap_and_interiors_still_progress_every_tick(self):
        fixture, per_tick = self.run_ticks(8, False, 8)
        bound = 8 + CONSUMERS - 1
        for index, tick in enumerate(per_tick):
            kinds = [kind for kind, _ in tick]
            self.assertLessEqual(len(tick), bound, (index, tick))
            self.assertGreaterEqual(kinds.count("interior"), 1, (index, tick))
            self.assertGreaterEqual(kinds.count("infected"), 1, (index, tick))
        self.assert_cursors(per_tick)

    def test_a_budget_larger_than_the_demand_forces_nothing_and_matches_the_old_per_module_totals(self):
        fixture, per_tick = self.run_ticks(32, True, 3)
        self.assertEqual(0, fixture.f.state.m_TickWork.HCStarved())
        self.assertEqual(12, len([1 for k, _ in per_tick[0] if k == "interior"]))
        self.assert_cursors(per_tick)

    def test_forced_units_are_counted_as_starved_in_the_window_report(self):
        fixture = TwoConsumerFixture(8, True)
        for _ in range(61):
            fixture.run_tick()
        lines = [line for line in fixture.f.profile.logs if "[HC TickWork] window=" in line]
        self.assertEqual(1, len(lines), lines)
        match = re.search(r"shared_used_max=(\d+) shared_starved=(\d+)", lines[0])
        self.assertEqual(9, int(match[1]))
        self.assertEqual(60, int(match[2]), "one forced infected unit in each of the 60 window ticks")


class OffPathTests(unittest.TestCase):
    """No core tick running: modules behave exactly as before the shared budget (their own caps only)."""

    def test_interiors_outside_a_core_tick_visit_every_site_once_per_tick(self):
        visits = []
        interior = search.SearchIntegrationTests()
        interior.setUp()
        interior.t.m_Sites = EArray(site_class(visits)(i) for i in range(12))
        interior.t.IsEnabled = lambda settings: settings.EnableInteriors
        for _ in range(2):
            visits.clear()
            interior.call("OnTick", 1.0)
            self.assertEqual([("interior", i) for i in range(12)], visits)

    def test_infected_outside_a_core_tick_are_limited_only_by_their_own_cap(self):
        h = infected.StartedModule(flags=infected.NO_ADMISSION, hordes=False).start()
        sampled = []
        h.ctx.m_Actors = infected.Array(Actor(i) for i in range(24))
        h.ctx.SampleActor = lambda actor: sampled.append(actor.index)
        h.ctx.FinishSweep = lambda now: None
        h.tick(10001)
        self.assertEqual(list(range(len(sampled))), sampled)
        self.assertGreater(len(sampled), 1)
        self.assertLessEqual(len(sampled), 30)


class SourceWiringTests(unittest.TestCase):
    def read(self, relative):
        return (SCRIPTS / relative).read_text()

    # Wave 14 (#195): the behaviour of every consumer id is executed in test_hc_tick_budget_fixes (houses
    # ChargeQuery/RecycleSpentBindings/CompactSettled, the refresh OnTick batch, the interiors lock loop and
    # CanStart) and by the two-consumer tests above (interiors, infected). This presence check stays as the
    # cheap guard that a loop was not re-pointed at another id, and that no consumer id is orphaned.
    def test_every_consumer_id_is_taken_by_exactly_the_loops_that_own_it(self):
        sources = "".join(path.read_text() for path in (SCRIPTS / "4_World").rglob("*.c"))
        for name in CONST:
            if name in ("HC_WORK_CONSUMERS", "HC_WORK_UNBOUNDED"):
                continue
            self.assertIn("HCTakeFor(HCUnitBudget." + name + ", 1)", sources, name)

    def test_every_consumer_loop_takes_a_unit_from_the_shared_budget(self):
        wiring = {
            "4_World/Infected/HCInfectedModule.c": ("HC_WORK_INFECTED",),
            "4_World/Interiors/HCInteriorModule.c": ("HC_WORK_INTERIORS",),
            "4_World/Loot/HCSearchHouses.c": ("HC_WORK_SEARCH_BIND", "HC_WORK_SEARCH_MAINT", "HC_WORK_SEARCH_DETACHED"),
            "4_World/Loot/HCSearchRefresh.c": ("HC_WORK_SEARCH_REFRESH", "HC_WORK_SEARCH_MAINT"),
        }
        for path, ids in wiring.items():
            text = self.read(path)
            self.assertIn("HCServer.HCTickWork()", text, path)
            for name in ids:
                self.assertRegex(text, r"HCTakeFor\(HCUnitBudget\." + name + r", 1\)", path + " " + name)

    def test_server_owns_one_budget_reset_before_the_module_loop_and_reports_per_window(self):
        text = self.read("4_World/Core/HCServer.c")
        self.assertRegex(text, r"protected ref HCUnitBudget m_TickWork = new HCUnitBudget\(\);")
        reset = text.index("m_TickWork.HCReset(m_Settings.MaxTickWorkItems)")
        loop = text.index("module.OnTick(elapsed)")
        self.assertLess(reset, loop)
        self.assertEqual(1, text.count("HCWindowReport()"))


if __name__ == "__main__":
    unittest.main()
