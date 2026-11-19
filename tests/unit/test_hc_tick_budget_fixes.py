"""Wave 14 / issue #195 ("Shared tick budget (#138)"): behavioural checks of the shared core-tick budget.

Executes the AUTHORED HCSearchHouses.RecycleSpentBindings / ChargeQuery, the authored
HCSearchHouses.CompactSettled (modded in HCSearchRefresh.c), the authored HCInteriorsModule.CanStart/OnTick
and the authored HCSearchRefreshModule.OnTick through the repo's syntax-only translators over explicit
SYNTHETIC fakes. Item counts, clocks and rows are offline evidence about control flow only; they say nothing
about DayZ timing or engine behaviour. runtime=PENDING until a native boot prints the '[HC TickWork]' line.
"""
import copy
import re
import unittest
from pathlib import Path
from types import SimpleNamespace as N

from tests.unit import test_search_economy_houses as houses
from tests.unit import test_search_economy_integration as integration
from tests.unit import tick_budget_fixture as tickbudget
from tests.unit.test_group_server import EArray
from tests.unit.test_v2_loot_refresh import SyntheticId

CONST = tickbudget.constants()
INFECTED = CONST.get("HC_WORK_INFECTED", 0)


def spent_budget(limit=1):
    """A synthetic shared budget whose pool is already used up by another consumer (INFECTED)."""
    budget = tickbudget.new_budget()
    budget.HCReset(limit)
    while budget.HCTakeFor(INFECTED, 1):
        pass
    return budget


def route_budget(env, budget):
    env["HCServer"].HCTickWork = lambda: budget


class RecycleStarvationTests(houses.HouseCase):
    """Both RecycleSpentBindings loops keep making progress when the shared pool is spent."""

    def settled_houses(self, count):
        out = []
        for n in range(count):
            house = self.h.house(position=(1000. + 100. * n, 0., 1000.))
            self.h.food(n + 1, houses.site_world(house, houses.SITE_A))
            player = self.h.player("p%d" % n)
            action = self.h.action(player, house, [0., 1., 0.], [0., 1., 1.])
            self.h.houses.Begin(action)
            self.h.world.now += 6.5
            self.h.houses.Commit(action)
            self.h.houses.End(action)
            out.append(player)
        far = self.h.player("far", position=(9000., 0., 9000.))
        return EArray([far])

    def test_the_detached_loop_releases_one_binding_per_tick_when_the_pool_is_spent(self):
        self.h = houses.Harness()
        far = self.settled_houses(2)
        self.assertEqual(2, self.h.houses.m_Journal.SiteCount())
        # One binding is already detached (its registry handles forgotten), one is still active.
        self.assertTrue(self.h.houses.ReleaseAt(0))
        self.assertEqual((1, 1), (len(self.h.houses.m_Slots), len(self.h.houses.m_DetachedSlots)))
        route_budget(self.h.env, spent_budget())
        self.h.houses.RecycleSpentBindings(far)
        # Active loop: its one forced unit moved the active slot to the detached list.
        self.assertEqual(0, len(self.h.houses.m_Slots))
        # Detached loop: its OWN forced unit released exactly one detached binding's journal site.
        self.assertEqual(1, len(self.h.houses.m_DetachedSlots))
        self.assertEqual(1, self.h.houses.m_Journal.SiteCount())
        # The next tick drains the last one: one binding per tick, never starved.
        route_budget(self.h.env, spent_budget())
        self.h.houses.RecycleSpentBindings(far)
        self.assertEqual(0, len(self.h.houses.m_DetachedSlots))
        self.assertEqual(0, self.h.houses.m_Journal.SiteCount())

    def test_detached_loop_uses_its_own_consumer_id_and_the_bound_counts_it(self):
        self.assertIn("HC_WORK_SEARCH_DETACHED", CONST)
        ids = [CONST[name] for name in CONST if name.startswith("HC_WORK_") and name not in
               ("HC_WORK_CONSUMERS", "HC_WORK_UNBOUNDED")]
        self.assertEqual(CONST["HC_WORK_CONSUMERS"], len(ids))
        self.assertEqual(8, CONST["HC_WORK_CONSUMERS"])
        for limit in (1, 4, 32):
            budget = tickbudget.new_budget()
            budget.HCReset(limit)
            total = 0
            for consumer in range(CONST["HC_WORK_CONSUMERS"]):
                while budget.HCTakeFor(consumer, 1):
                    total += 1
            self.assertEqual(limit + CONST["HC_WORK_CONSUMERS"] - 1, total)


class ExpiredLockTests(unittest.TestCase):
    """HCInteriorsModule.CanStart treats an owner whose lock deadline has passed as free (#195)."""

    def setUp(self):
        self.t = integration.SearchIntegrationTests()
        self.t.setUp()
        self.t.t.m_Economy = N(CanGrant=lambda site_id, player: True)
        self.t.t.m_Ready = True
        self.t.t.m_SearchProof = True
        self.t.t.m_Store = N(Healthy=lambda: True)
        self.t.t.m_Sites = EArray([self.t.site])

    def start(self):
        return self.t.call("CanStart", self.t.actor, self.t.target)

    def test_a_free_site_starts(self):
        # Guards the other tests: the harness itself admits a start, so their refusals are about the lock.
        self.t.site.Owner = None
        self.assertTrue(self.start())

    def test_a_live_lock_still_refuses_busy(self):
        # Synthetic clock 100.0, deadline 105.0: the owner is live.
        self.assertIsNotNone(self.t.site.Owner)
        self.assertFalse(self.start())
        self.assertIsNotNone(self.t.site.Owner)

    def test_an_expired_lock_is_cleared_and_the_new_search_starts(self):
        self.t.now = 106.0
        self.assertTrue(self.start())
        self.assertIsNone(self.t.site.Owner)

    def test_the_deadline_itself_is_still_live(self):
        # The expiry loop uses `now > Deadline`; CanStart shares that code path.
        self.t.now = 105.0
        self.assertFalse(self.start())
        self.assertIsNotNone(self.t.site.Owner)

    def test_the_tick_loop_and_can_start_share_one_expiry_method(self):
        source = (tickbudget.SCRIPTS / "4_World/Interiors/HCInteriorModule.c").read_text()
        self.assertEqual(1, source.count("lockSite.Owner = null"), "one expiry body")
        self.assertIn("ExpireLock(lockSite)", source)
        self.assertRegex(source, r"ExpireLock\(site\);\s*if \(site\.Owner\)")


class RefreshHarness:
    """The authored HCSearchRefreshModule (+ policy/row/state classes) over synthetic ports.

    Mechanical syntax adapters only (the same ones as test_v2_loot_refresh); the batch/cursor/save policy
    under test is the authored OnTick.
    """
    SOURCE = tickbudget.SCRIPTS / "4_World/Loot/HCSearchRefresh.c"

    def __init__(self, rows, per_tick_pool, max_items=32):
        source = self.SOURCE.read_text()
        source = source.replace("bool onlyMissing = false", "bool onlyMissing")
        source = source.replace("alphabet.IndexOf(siteId.Get(index))", "alphabet.find(siteId[index])")
        source = source.replace("m_Pending--", "m_Pending = m_Pending - 1")
        source = source.replace("m_Refreshed++", "m_Refreshed = m_Refreshed + 1")
        self.utc = 1000
        self.saved = []
        self.printed = []

        class RefreshSyntax(houses.Translator):
            def expr(self, text, names):
                return super().expr(text, names).replace("self.s_Instance", "_refresh_state.s_Instance")

        self.env = dict(HCModule=object, HCOperationalStatus=object, EArray=houses.EArray, HMap=houses.HMap, find_out=houses.find_out,
                        Print=self.printed.append, HCGroupClock=N(Utc=lambda: self.utc),
                        _refresh_state=N(s_Instance=None),
                        HCSearchRules=N(TextValid=lambda value, cap: bool(value) and len(value) <= cap))
        tickbudget.install(self.env)
        self.budget = tickbudget.new_budget()
        self.env["HCServer"].HCTickWork = lambda: self.budget
        for code in RefreshSyntax(source, only=("HCSearchRefreshRow", "HCSearchRefreshState", "HCSearchRefreshPolicy",
                                                "HCSearchRefreshModule")).classes():
            exec(code, self.env)
        self.module = self.env["HCSearchRefreshModule"]()
        self.module.m_Settings = N(EnableWorld=True, MaxTickWorkItems=max_items)
        self.module.m_State = self.env["HCSearchRefreshState"]()
        self.module.m_State.LastUtc = 1000
        self.module.m_Store = N(Healthy=lambda: True, Fault=lambda: self.printed.append("fault"),
                                Save=lambda state: self.saved.append(copy.deepcopy(state)) or True)
        self.env["_refresh_state"].s_Instance = self.module
        self.pool = per_tick_pool
        for number in range(rows):
            row = self.env["HCSearchRefreshRow"]()
            row.Scope, row.SiteId, row.SearchedUtc = "synthetic_scope", SyntheticId("synthetic_site_%d" % number), 100
            self.module.m_State.Rows.Insert(row)
            self.module.m_Index.Set(self.module.Key(row.Scope, row.SiteId), number)
            self.module.m_Pending += 1

    def tick(self, dt=1.0):
        """One core tick: a fresh shared budget of `pool` units, then the module's OnTick."""
        self.budget.HCReset(self.pool)
        self.module.OnTick(dt)

    def minute(self, dt=60.0):
        self.tick(dt)


class RefreshBatchResumeTests(unittest.TestCase):
    # Synthetic rows were searched at UTC 100; with the clock at 1000 they are not yet due, so we move the
    # clock past the longest synthetic interval (4 days) to make every row due.
    DUE_UTC = 100 + 5 * 86400

    def harness(self, rows, pool):
        h = RefreshHarness(rows, pool)
        h.utc = self.DUE_UTC
        return h

    def test_a_batch_larger_than_the_pool_resumes_and_refreshes_every_row_exactly_once(self):
        h = self.harness(rows=6, pool=1)
        h.minute()
        self.assertEqual(1, h.module.m_Refreshed)
        self.assertEqual(5, h.module.m_BatchLeft)
        self.assertEqual([], h.saved, "no save while the batch is unfinished")
        self.assertEqual(1000, h.module.m_State.LastUtc, "LastUtc advances only when the batch ends")
        ticks = 0
        while h.module.m_BatchLeft > 0 and ticks < 20:
            h.tick()
            ticks += 1
        self.assertEqual(5, ticks)
        self.assertEqual(6, h.module.m_Refreshed)
        self.assertEqual(0, h.module.m_Pending)
        self.assertTrue(all(row.Ready and row.Revisited for row in h.module.m_State.Rows))
        self.assertEqual(1, len(h.saved), "exactly one save, at the end of the batch")
        self.assertEqual(self.DUE_UTC, h.module.m_State.LastUtc)
        self.assertEqual(self.DUE_UTC, h.saved[0].LastUtc)

    def test_a_new_minute_arriving_mid_batch_is_held_until_the_batch_ends(self):
        h = self.harness(rows=4, pool=1)
        h.minute()
        self.assertEqual(3, h.module.m_BatchLeft)
        # Another full minute of game time arrives while three rows are still owed.
        h.tick(61.0)
        self.assertEqual(2, h.module.m_BatchLeft, "the owed batch continues; no second batch started")
        self.assertGreaterEqual(h.module.m_Minute, 61.0, "the pending minute is held, not discarded")
        h.tick()
        h.tick()
        self.assertEqual(0, h.module.m_BatchLeft)
        self.assertEqual(4, h.module.m_Refreshed)
        self.assertEqual(1, len(h.saved))
        # The held minute starts the next batch on the very next tick (rows are already Ready: no change).
        h.tick()
        self.assertLess(h.module.m_Minute, 60.0)
        self.assertEqual(4, h.module.m_Refreshed)
        self.assertEqual(1, len(h.saved), "a batch with no change saves nothing")

    def test_rows_not_yet_due_advance_the_cursor_without_a_save(self):
        h = RefreshHarness(3, 1)
        h.minute()
        self.assertEqual(2, h.module.m_BatchLeft)
        h.tick()
        h.tick()
        self.assertEqual(0, h.module.m_BatchLeft)
        self.assertEqual(0, h.module.m_Refreshed)
        self.assertEqual([], h.saved)
        self.assertEqual(1000, h.module.m_State.LastUtc)

    def test_a_roomy_pool_finishes_the_batch_in_one_tick_with_one_save(self):
        h = self.harness(rows=6, pool=64)
        h.minute()
        self.assertEqual(0, h.module.m_BatchLeft)
        self.assertEqual(6, h.module.m_Refreshed)
        self.assertEqual(1, len(h.saved))

    def test_a_clock_that_went_backwards_faults_instead_of_saving(self):
        h = self.harness(rows=2, pool=1)
        h.minute()
        h.utc = 500
        h.tick()
        self.assertIn("fault", h.printed)
        self.assertEqual([], h.saved)


class ModdedLinkTranslator(houses.Translator):
    """Translator for a `modded class` link: names of members declared by the BASE link resolve to self.*.

    The base member names are read from the authored base sources (not retyped); nothing else changes.
    """
    BASE_FILES = ("HCSearchHouses.c", "HCSearchHouseJournal.c")

    def __init__(self, source, only=None):
        super().__init__(source, only)
        base = "".join((houses.LOOT / name).read_text() for name in self.BASE_FILES)
        self.base_names = set(re.findall(r"\b(m_\w+)\b", base))
        self.base_names |= set(re.findall(r"^\s+(?:override |static |protected )*[\w<>]+ (\w+)\(", base, re.M))

    def block(self, text, names, indent):
        return super().block(text, set(names) | self.base_names, indent)

    def expr(self, text, names):
        return super().expr(text, set(names) | self.base_names)


class HouseBudgetCase(houses.HouseCase):
    """ChargeQuery and CompactSettled (modded in HCSearchRefresh.c) over the houses harness."""

    def with_refresh_mods(self, **settings_override):
        self.h = houses.Harness(**settings_override)
        env = self.h.env
        self.marks = []
        env["HCSearchRefreshModule"] = N(
            Mark=lambda scope, site, only=False: self.marks.append(("mark", site, only)),
            Ready=lambda scope, site: False,
            ForgetCompacted=lambda scope, site: self.marks.append(("forget", site)))
        source = (tickbudget.SCRIPTS / "4_World/Loot/HCSearchRefresh.c").read_text()
        env["Math"] = N(AbsFloat=abs, Min=min)
        env["_Base_HCSearchHouses"] = env["HCSearchHouses"]
        env["_Base_HCSearchHouseJournal"] = env["HCSearchHouseJournal"]
        for code in ModdedLinkTranslator(source, only=("HCSearchHouses", "HCSearchHouseJournal")).classes():
            exec(code, env)
        for name in ("HCSearchHouses", "HCSearchHouseJournal"):
            self.chain_init(env[name], env["_Base_" + name])
        # A new process lifetime over the modded classes (journal and files survive in the harness fs).
        self.h.houses = env["HCSearchHouses"]()
        self.h.houses.Start(self.h.settings)
        self.h.houses_binding.houses = self.h.houses
        return self.h

    @staticmethod
    def chain_init(sub, base):
        """The translator emits one flat __init__ per class; a modded link runs its base link's first."""
        own = sub.__init__

        def init(self):
            base.__init__(self)
            own(self)
        sub.__init__ = init

    def settled_houses(self, count):
        return RecycleStarvationTests.settled_houses(self, count)

    def test_charge_query_takes_a_shared_unit_and_stays_inside_its_own_cap(self):
        self.h = houses.Harness()
        # Roomy pool: the per-tick own cap (MaxBindQueriesPerTick=2) is the only limit.
        roomy = tickbudget.new_budget()
        roomy.HCReset(32)
        route_budget(self.h.env, roomy)
        self.assertEqual([True, True, False], [self.h.houses.ChargeQuery() for _ in range(3)])
        self.assertEqual(2, roomy.HCUsed(), "each scan took exactly one shared unit")
        # A new tick clock value reopens the own window.
        self.h.world.now += 1.0
        self.assertTrue(self.h.houses.ChargeQuery())

    def test_charge_query_under_a_spent_pool_is_forced_once_per_tick(self):
        self.h = houses.Harness()
        budget = spent_budget()
        route_budget(self.h.env, budget)
        self.assertEqual([True, False, False], [self.h.houses.ChargeQuery() for _ in range(3)])
        self.assertEqual(1, budget.HCStarved())

    def test_charge_query_outside_a_core_tick_is_limited_only_by_its_own_cap(self):
        self.h = houses.Harness()
        # The harness default is the idle budget (no HCServer instance): it never refuses.
        self.assertEqual([True, True, False], [self.h.houses.ChargeQuery() for _ in range(3)])

    def test_compact_settled_examines_one_forced_row_per_tick_and_resumes_at_the_refused_row(self):
        self.with_refresh_mods()
        self.settled_houses(3)
        journal = self.h.houses.m_Journal
        # Explicit synthetic port: the legacy-tombstone prune is journal file I/O, not budget logic.
        journal.PruneLegacyTombstones = lambda limit: True
        self.assertEqual(3, journal.Count(), 'three synthetic claim rows')
        self.h.houses.m_CompactNext = 0
        starts = []
        for _ in range(3):
            route_budget(self.h.env, spent_budget())
            self.h.houses.CompactSettled()
            starts.append(self.h.houses.m_CompactNext)
        # One forced row per tick; the cursor wraps to row 0 after the last row (refused rows are never skipped).
        self.assertEqual([1, 2, 0], starts)

    def test_compact_settled_under_a_roomy_pool_examines_every_row_once_per_call(self):
        self.with_refresh_mods()
        self.settled_houses(3)
        self.h.houses.m_Journal.PruneLegacyTombstones = lambda limit: True
        count = self.h.houses.m_Journal.Count()
        self.h.houses.m_CompactNext = 0
        budget = tickbudget.new_budget()
        budget.HCReset(32)
        route_budget(self.h.env, budget)
        self.h.houses.CompactSettled()
        self.assertEqual(count, budget.HCUsed())
        self.assertEqual(count, budget.HCItems())


if __name__ == "__main__":
    unittest.main()
