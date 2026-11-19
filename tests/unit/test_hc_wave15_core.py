"""Wave 15 / issue #196 (w31-p3core): shared tick budget and debug map P3s, executed behaviourally.

Executes the AUTHORED HCServer.Tick/Stop (test_v1_combined_flags.CoreFixture), the authored
HCInteriorsModule search methods and the authored HCPickers debug getters through the repo's
syntax-only translators over explicit SYNTHETIC fakes. Nothing here observes DayZ; runtime=PENDING.
"""
import re
import unittest
from pathlib import Path
from types import SimpleNamespace as N

from tests.unit import test_event_runtime as event
from tests.unit import test_search_economy_integration as integration
from tests.unit import test_v1_combined_flags as combined
from tests.unit import test_debug_map_layers as layers
from tests.unit.test_admin_test_kit import base_scope
from tests.unit.test_group_server import EArray


class StopInsideTickTests(unittest.TestCase):
    """A module that stops the core from inside OnTick ends the tick for every later module."""

    def fixture(self):
        f = combined.CoreFixture()
        f.state.Start()
        self.assertGreaterEqual(len(f.state.m_Active), 3)
        f.perf_samples = []
        f.state.m_Perf.Sample = lambda elapsed, ticks: f.perf_samples.append(ticks)
        f.state.m_Perf.SampleModule = lambda index, ticks: f.perf_samples.append(("module", index))
        f.window_ticks = []
        original = f.state.m_TickWork.HCEndTick
        f.state.m_TickWork.HCEndTick = lambda elapsed, seconds: (f.window_ticks.append(elapsed),
                                                                  original(elapsed, seconds))[1]
        return f

    def test_modules_after_a_stopping_module_are_not_ticked_and_the_window_is_not_rolled(self):
        f = self.fixture()
        stopper = f.state.m_Active[1]
        order = [m.GetName() for m in f.state.m_Active]
        stopper.OnTick = lambda elapsed: (f.work.append(stopper.GetName()), f.state.Stop())
        f.now += 1
        f.state.Tick()
        self.assertEqual(order[:2], f.work)
        self.assertFalse(f.state.m_Started)
        self.assertFalse(f.state.m_TickActive)
        self.assertEqual([], f.window_ticks, "the budget window must not roll on a stopped tick")
        self.assertEqual([("module", 0)], f.perf_samples, "no perf sample after Stop retired the sampler")

    def test_a_later_tick_callback_does_nothing_after_the_stop(self):
        f = self.fixture()
        f.state.m_Active[0].OnTick = lambda elapsed: f.state.Stop()
        f.now += 1
        f.state.Tick()
        f.work.clear()
        f.now += 1
        f.state.Tick()
        self.assertEqual([], f.work)

    def test_an_ordinary_tick_still_runs_every_module_once_and_rolls_the_window(self):
        f = self.fixture()
        f.now += 1
        f.state.Tick()
        self.assertEqual(sorted(m.GetName() for m in f.state.m_Active), sorted(f.work))
        self.assertEqual(1, len(f.window_ticks))
        self.assertEqual(len(f.state.m_Active) + 1, len(f.perf_samples))


class StaleSearchSessionTests(unittest.TestCase):
    """A's lock expires, B starts on the same site, then A's late calls arrive (#196 P3)."""

    def setUp(self):
        self.t = integration.SearchIntegrationTests()
        self.t.setUp()
        self.t.t.m_Sites = EArray([self.t.site])
        self.site = self.t.site
        self.a = self.t.data
        self.player_b = N(IsAlive=lambda: True, IsUnconscious=lambda: False,
                          MessageStatus=lambda msg: self.t.events.append(("message", msg)))
        self.player_b.GetIdentity = lambda: N(GetId=lambda: "actor_b", GetPlayer=lambda: self.player_b)
        self.b = integration.NativeRef(player_arg=self.player_b, target_arg=self.t.target, Site=None)
        self.grants = lambda: [e for e in self.t.events if isinstance(e, tuple) and e[0] == "grant"]

    def b_takes_over(self):
        # SYNTHETIC clock: A's deadline is 105.0; B starts after it.
        self.t.now = 106.0
        self.t.call("BeginSearch", self.b)
        self.assertIs(self.b, self.site.Owner)
        self.assertIs(self.site, self.b.Site)
        self.assertTrue(self.t.call("SessionValid", self.b, self.site))

    def test_a_late_continue_and_commit_cannot_grant_or_take_the_site_back(self):
        self.b_takes_over()
        self.t.now = 112.0
        self.assertFalse(self.t.call("CanContinue", self.a))
        self.t.call("CommitSearch", self.a)
        self.assertEqual([], self.grants())
        self.assertIs(self.b, self.site.Owner)
        self.assertFalse(self.t.call("SessionValid", self.a, self.site))
        self.assertTrue(self.t.call("SessionValid", self.b, self.site))

    def test_a_late_end_cannot_clear_the_new_owner_or_session(self):
        self.b_takes_over()
        self.t.call("EndSearch", self.a)
        self.assertIsNone(self.a.Site)
        self.assertIs(self.b, self.site.Owner)
        self.assertTrue(self.t.call("SessionValid", self.b, self.site))
        self.assertEqual(1, len(self.t.t.m_SearchSessions))

    def test_b_still_grants_exactly_once_after_every_late_call_from_a(self):
        self.b_takes_over()
        self.t.now = 112.0
        self.t.call("CommitSearch", self.a)
        self.t.call("EndSearch", self.a)
        self.t.call("CommitSearch", self.a)
        self.t.call("CommitSearch", self.b)
        self.t.call("CommitSearch", self.b)
        self.t.call("CommitSearch", self.a)
        granted = self.grants()
        self.assertEqual(1, len(granted))
        self.assertIs(self.player_b, granted[0][2])
        self.assertEqual(2, self.site.Phase)


class PickerGettersWithoutATripTests(unittest.TestCase):
    """HCPickers debug getters before the journal object exists (m_Trip null) report no rows (#196 P3)."""

    def getters(self):
        scope = base_scope(HCDebugPickerRow=lambda: N(Locator="none", HasPosition=False),
                           HCDebugSnapshot=N(**layers.CONSTANTS))
        count = layers.compile_authored(layers.PICKERS, "HCPickers", "HCDebugPickerCount", scope, modded=False)
        row = layers.compile_authored(layers.PICKERS, "HCPickers", "HCDebugPicker", scope, modded=False)
        return count, row

    def test_a_null_trip_has_zero_rows_and_no_picker_zero(self):
        count, row = self.getters()
        receiver = N(m_Trip=None)
        self.assertEqual(0, count(receiver))
        for wanted in (-1, 0, 1, 99):
            self.assertIsNone(row(receiver, wanted), wanted)

    def test_a_trip_with_no_state_or_no_inventory_port_also_has_zero_rows(self):
        count, row = self.getters()
        stateless = N(m_Trip=N(m_Ready=True, m_State=None, m_IO=None))
        self.assertEqual(0, count(stateless))
        self.assertIsNone(row(stateless, 0))
        portless = N(m_Trip=N(m_Ready=True, m_State=N(Phase="leaving", Generation=1, Refusal=""), m_IO=None))
        self.assertIsNone(row(portless, 0))


GROUP_IO = Path(__file__).resolve().parents[2] / "mods/HollowCountry/scripts/3_Game/Groups/HCGroupIO.c"


class RawReadCapTests(unittest.TestCase):
    """HCGroupIO names its raw read/write cap once and reads it qualified (#196 P3)."""

    def setUp(self):
        self.text = GROUP_IO.read_text()
        found = re.search(r"static const int (\w+) = (\d+);", self.text)
        self.assertIsNotNone(found, "HCGroupIO must declare the cap as a static const")
        self.name, self.cap = found[1], int(found[2])
        self.opened = []
        # Translator shim: the syntax-only port drops typed locals except the ones it knows.
        self.text = self.text.replace("FileHandle handle", "handle")

    def env(self):
        group_io = N(**{self.name: self.cap})
        return dict(HCGroupIO=group_io, FileMode=N(READ=0, WRITE=1),
                    OpenFile=lambda path, mode: self.opened.append(path),
                    FileExist=lambda path: True,
                    HCRecoveryGate=N(HCAllowWrite=lambda path: True))

    def test_the_cap_is_one_named_constant_and_the_bare_literal_appears_once(self):
        self.assertEqual(1048576, self.cap)
        self.assertEqual(1, self.text.count("1048576"), "only the declaration may carry the number")
        self.assertEqual(2, self.text.count("limit > HCGroupIO." + self.name), "read and write gates, qualified")

    def test_a_limit_above_the_cap_is_refused_before_any_file_is_opened(self):
        read = event.translate(self.text, "HCReadRaw", self.env())
        self.assertFalse(read("p", self.cap + 1, ""))
        self.assertFalse(read("p", 0, ""))
        self.assertEqual([], self.opened)

    def test_a_limit_equal_to_the_cap_is_admitted_to_the_open(self):
        read = event.translate(self.text, "HCReadRaw", self.env())
        self.assertFalse(read("p", self.cap, ""), "the open port returns null here")
        self.assertEqual(["p"], self.opened)

    def test_write_new_refuses_a_limit_above_the_cap_before_the_existence_check(self):
        env = self.env()
        env["FileExist"] = lambda path: self.fail("the cap gate runs before FileExist")
        write = event.translate(self.text, "WriteNew", env)
        self.assertFalse(write("p", "x", self.cap + 1))


if __name__ == "__main__":
    unittest.main()
