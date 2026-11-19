"""Issue #138: bounded per-tick work for Ecology, WorldSaves and Interiors furnishing.

Offline contract tests. The authored Enforce methods are translated by the repo's syntax-only
translator and run against EXPLICIT SYNTHETIC ports (a fake file system, fake clock/TickCount, fake
jobs). Nothing here measures DayZ time or proves a tick stays under any millisecond figure: the unit
budgets bound WORK (files, pairs, creation attempts), and the runtime cost per unit stays PENDING until
the [HC Perf] / [HC Save] lines of a native boot are compared.

RED (2026-11-18, before the WorldSaves/Interiors changes; HCUnitBudget already existed):
  PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.unit.test_hc_unit_budget
  -> Ran 29 tests, FAILED (failures=12, errors=8): scheduler had no HCStep/HCInFlight/stages, the
     store had no SaveStep/Encode/SaveInFlight, the world module no HCStepRoutine.
GREEN: the same command, Ran 29 tests, OK.

Round 2 (2026-11-18, boot 028 evidence: Interiors 63-140 ms ticks, Scenes save one 1314540-tick stage):
RED  PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.unit.test_hc_unit_budget
  -> Ran 52 tests, FAILED (failures=22, errors=5): no HCUnitBudget.HCChargeMeasured, no
     Core/HCStepTimer.c, no HCSceneChainStore.SaveStep, no slowest_stage= in the [HC Save] line, the
     Interiors module had no HCFurnish/measured charge and the scene job no HCStep.
GREEN the same command, Ran 52 tests, OK. The sub-timer and measured charge use SYNTHETIC tick
values; real per-step costs come only from the '[HC Step] owner=Interiors' line of a native boot.
"""
import re
from pathlib import Path
from types import SimpleNamespace as N
import unittest

from tests.unit.test_event_runtime import translate as event_translate
from tests.unit.test_group_server import EArray

SCRIPTS = Path(__file__).resolve().parents[2] / "mods/HollowCountry/scripts"
BUDGET = SCRIPTS / "4_World/Core/HCUnitBudget.c"
WORKBUDGET = SCRIPTS / "4_World/World/HCWorkBudget.c"
STORE = SCRIPTS / "4_World/World/HCWorldStore.c"
WORLD_MODULE = SCRIPTS / "4_World/World/HCWorldModule.c"
INTERIOR_MODULE = SCRIPTS / "4_World/Interiors/HCInteriorTemplatesModule.c"
INTERIOR_CURSOR = SCRIPTS / "4_World/Interiors/HCInteriorPlacementCursor.c"
INTERIOR_TEMPLATES = SCRIPTS / "4_World/Interiors/HCInteriorTemplates.c"
INTERIOR_PLACEMENT = SCRIPTS / "4_World/Interiors/HCInteriorTemplatePlacement.c"
STEP_TIMER = SCRIPTS / "4_World/Core/HCStepTimer.c"
SCENE_CHAINS = SCRIPTS / "4_World/Scenes/HCSceneChains.c"
SCENES_MODULE = SCRIPTS / "4_World/Scenes/HCScenesModule.c"

RENAMES = ("HCSaveJob", "HCWorldData", "HCUnitBudget", "HCStepTimer", "HCSceneChainState")


def translated(text, name, env, owner, member=True, integer_division=False):
    """Syntax-only translation of one authored method (types that the translator does not know
    about are renamed to the HCEvent prefix it strips). integer_division maps Enforce int '/' (truncating)."""
    renamed = text
    if integer_division:
        # The translator strips '//' as a comment, so Enforce int division becomes a helper call.
        renamed = re.sub(r"(\w+) / (\w+)", r"int_div(\1, \2)", renamed)
        env = dict(env, int_div=lambda a, b: int(a / b))
    for cls in RENAMES:
        renamed = re.sub(r"\b" + cls + r"\b", "HCEvent" + cls[2:], renamed)
    renamed = re.sub(r"\bthis\b", "self", renamed)
    renamed = re.sub(r"(\b[\w.]+)\+\+;", r"\1 += 1;", renamed)
    renamed = re.sub(r"(\b[\w.]+)--;", r"\1 -= 1;", renamed)
    renamed_env = {}
    for key, value in env.items():
        for cls in RENAMES:
            if key == cls:
                key = "HCEvent" + cls[2:]
        renamed_env[key] = value
    return event_translate(renamed, name, renamed_env, owner, member)


def constants(text):
    return {m[1]: int(m[2]) for m in re.finditer(r"static const int (\w+) = (\d+);", text)}


def unit_budget():
    text = BUDGET.read_text()
    budget = N(m_Limit=0, m_Used=0, m_Items=0)
    import functools
    for name in ("HCReset", "HCTake", "HCCharge", "HCExhausted", "HCUsed", "HCLimit", "HCItems", "HCChargeMeasured"):
        if name == "HCChargeMeasured" and "HCChargeMeasured(" not in text:
            raise AssertionError("Missing authored method HCChargeMeasured")
        setattr(budget, name, functools.partial(translated(text, name, {}, "HCUnitBudget", integer_division=True), budget))
    return budget


class UnitBudgetTests(unittest.TestCase):
    def test_items_are_admitted_until_the_units_are_spent(self):
        # SYNTHETIC unit costs: 1 per cheap row, 8 per creation attempt.
        budget = unit_budget()
        budget.HCReset(20)
        taken = [budget.HCTake(8), budget.HCTake(8), budget.HCTake(8), budget.HCTake(1)]
        self.assertEqual([True, True, False, True], taken)
        self.assertEqual((17, 3), (budget.HCUsed(), budget.HCItems()))
        self.assertTrue(budget.HCTake(3))
        self.assertTrue(budget.HCExhausted())
        self.assertFalse(budget.HCTake(1))

    def test_an_item_heavier_than_the_whole_budget_still_makes_progress_once_per_tick(self):
        budget = unit_budget()
        budget.HCReset(5)
        self.assertTrue(budget.HCTake(500))
        self.assertFalse(budget.HCTake(1))
        budget.HCReset(5)
        self.assertTrue(budget.HCTake(500))

    def test_costs_below_one_count_as_one_and_limits_below_one_become_one(self):
        budget = unit_budget()
        budget.HCReset(0)
        self.assertEqual(1, budget.HCLimit())
        self.assertTrue(budget.HCTake(0))
        self.assertEqual(1, budget.HCUsed())
        self.assertFalse(budget.HCTake(-4))

    def test_post_hoc_charge_closes_the_slice_and_ignores_non_positive_costs(self):
        budget = unit_budget()
        budget.HCReset(10)
        self.assertTrue(budget.HCTake(1))
        budget.HCCharge(0)
        budget.HCCharge(-3)
        self.assertEqual(1, budget.HCUsed())
        budget.HCCharge(9)
        self.assertTrue(budget.HCExhausted())
        self.assertFalse(budget.HCTake(1))

    def test_measured_charge_takes_the_larger_of_declared_and_measured_units(self):
        # SYNTHETIC: 4000 raw ticks per unit. The caller measured the item; the budget stays clock free.
        budget = unit_budget()
        budget.HCReset(24)
        self.assertTrue(budget.HCTake(1))
        budget.HCChargeMeasured(8, 20000, 4000, 1)   # 5 measured units < 8 declared
        self.assertEqual(8, budget.HCUsed())
        self.assertTrue(budget.HCTake(1))
        budget.HCChargeMeasured(8, 450000, 4000, 1)  # 112 measured units > 8 declared
        self.assertEqual(8 + 112, budget.HCUsed())
        self.assertFalse(budget.HCTake(1))
        budget.HCReset(24)
        self.assertTrue(budget.HCTake(1))
        budget.HCChargeMeasured(1, -5, 4000, 1)       # bad clock or zero divisor never refunds units
        budget.HCChargeMeasured(1, 9000, 0, 1)
        self.assertEqual(1, budget.HCUsed())

    def test_budget_has_no_engine_clock_or_allocation(self):
        text = BUDGET.read_text()
        for forbidden in ("GetGame", "GetTickTime", "TickCount", "new ", "Print("):
            self.assertNotIn(forbidden, re.sub(r"//[^\n]*", "", text), forbidden)


class FakeJob:
    """SYNTHETIC save job: a scripted list of step results; records every HCStep call."""

    def __init__(self, name, results, env):
        self.name = name
        self.results = list(results)
        self.HCDirty = True
        self.HCDue = 0.0
        self.HCInFlight = False
        self.HCPeakTicks = 0
        self.calls = 0
        self.env = env

    def HCName(self):
        return self.name

    def HCStep(self):
        self.calls += 1
        result = self.results.pop(0)
        self.HCInFlight = result == self.env["HCSaveJob"].STEP_MORE
        return result


class SchedulerHarness(unittest.TestCase):
    def setUp(self):
        text = WORKBUDGET.read_text()
        self.consts = constants(text)
        self.logs = []
        self.now = [100.0]
        self.clock = [0]
        self.env = dict(
            EArray=EArray, len=len, str=str, Print=self.logs.append,
            HCSaveJob=N(**self.consts), s_Jobs=EArray(),
            GetGame=lambda: N(GetTickTime=lambda: self.now[0]),
            TickCount=self.tick_count,
            Math=N(Max=max, Min=min),
        )
        self.sched = N(m_Next=0, m_Active=None, m_StageTicks=0, m_StageMax=0, m_StageMaxIndex=0, m_Stages=0, m_TotalTicks=0)
        # Static and instance methods of the scheduler resolve to self.<name>.
        for name in ("HCUnregister", "HCFlush", "HCRunStep", "HCRecordStage", "HCFinishSave"):
            if re.search(r"\b" + name + r"\(", text):
                setattr(self.sched, name, self.lazy(text, name))
        self.sched.GetName = lambda: "WorldSaves"
        self.sched.m_Budget = N(HCReset=lambda *a: None, HCContinue=lambda: True, HCDeferred=lambda *a: None)
        self.sched.HCRegister = lambda job: self.env["s_Jobs"].Insert(job)

    def tick_count(self, prev):
        # Synthetic: every TickCount(start) reports the ticks scripted by the test.
        return self.clock[0]

    def lazy(self, text, name):
        function = [None]

        def call(*args):
            if function[0] is None:
                function[0] = translated(text, name, self.env, "HCSaveScheduler")
            return function[0](self.sched, *args)
        return call

    def on_tick(self):
        translated(WORKBUDGET.read_text(), "OnTick", self.env, "HCSaveScheduler")(self.sched, 1.0)


class SaveSchedulerStagedTests(SchedulerHarness):
    def test_one_stage_per_tick_and_an_in_flight_job_is_not_interleaved(self):
        # SYNTHETIC: job A needs three stages; job B (also dirty and due) must wait for A to finish.
        done, more = self.consts["STEP_DONE"], self.consts["STEP_MORE"]
        a = FakeJob("World", [more, more, done], self.env)
        b = FakeJob("Scenes", [done], self.env)
        self.env["s_Jobs"].Insert(a)
        self.env["s_Jobs"].Insert(b)
        self.on_tick()
        self.assertEqual((1, 0), (a.calls, b.calls))
        self.assertTrue(a.HCInFlight)
        self.on_tick()
        self.assertEqual((2, 0), (a.calls, b.calls))
        self.on_tick()
        self.assertEqual((3, 0), (a.calls, b.calls))
        self.assertFalse(a.HCInFlight)
        self.assertFalse(a.HCDirty)
        self.assertEqual(160.0, a.HCDue)
        self.on_tick()
        self.assertEqual((3, 1), (a.calls, b.calls))

    def test_a_failed_stage_unregisters_the_job_without_retrying_every_tick(self):
        fail = self.consts["STEP_FAILED"]
        a = FakeJob("World", [self.consts["STEP_MORE"], fail], self.env)
        self.env["s_Jobs"].Insert(a)
        self.on_tick()
        self.on_tick()
        self.assertEqual(2, a.calls)
        self.assertEqual(0, len(self.env["s_Jobs"]))
        self.on_tick()
        self.assertEqual(2, a.calls)

    def test_synchronous_flush_finishes_every_remaining_stage(self):
        done, more = self.consts["STEP_DONE"], self.consts["STEP_MORE"]
        a = FakeJob("World", [more, more, done], self.env)
        self.env["s_Jobs"].Insert(a)
        self.on_tick()
        self.assertTrue(a.HCInFlight)
        self.assertTrue(self.sched.HCFlush(a))
        self.assertEqual(3, a.calls)
        self.assertEqual((False, False), (a.HCInFlight, a.HCDirty))

    def test_synchronous_flush_reports_a_failed_stage_and_a_clean_job_is_a_no_op(self):
        a = FakeJob("World", [self.consts["STEP_FAILED"]], self.env)
        self.assertFalse(self.sched.HCFlush(a))
        clean = FakeJob("Scenes", [], self.env)
        clean.HCDirty = False
        self.assertTrue(self.sched.HCFlush(clean))
        self.assertEqual(0, clean.calls)

    def test_flush_gives_up_on_a_job_that_never_finishes(self):
        more = self.consts["STEP_MORE"]
        a = FakeJob("World", [more] * 64, self.env)
        self.assertFalse(self.sched.HCFlush(a))
        self.assertLessEqual(a.calls, 16)

    def test_a_completed_save_logs_stages_and_the_slowest_stage_in_raw_ticks(self):
        done, more = self.consts["STEP_DONE"], self.consts["STEP_MORE"]
        a = FakeJob("World", [more, more, done], self.env)
        self.env["s_Jobs"].Insert(a)
        for ticks in (200, 900, 400):
            self.clock[0] = ticks
            self.on_tick()
        line = [entry for entry in self.logs if entry.startswith("[HC Save]")]
        self.assertEqual(1, len(line), self.logs)
        self.assertIn("job=World", line[0])
        self.assertIn("stages=3", line[0])
        self.assertIn("max_stage_ticks=900", line[0])
        self.assertIn("total_ticks=1500", line[0])
        self.assertIn("slowest_stage=2", line[0])
        self.assertNotIn("[HC Perf]", line[0])

    def test_a_job_dropped_mid_save_does_not_leak_its_stage_counts_into_the_next_save(self):
        # SYNTHETIC: a synchronous barrier write completes job A outside the scheduler (HCInFlight
        # cleared), so the next tick drops A; job B's line must report only its own stage.
        done, more = self.consts["STEP_DONE"], self.consts["STEP_MORE"]
        a = FakeJob("Scenes", [more, more, more, done], self.env)
        b = FakeJob("World", [done], self.env)
        self.env["s_Jobs"].Insert(a)
        self.env["s_Jobs"].Insert(b)
        self.clock[0] = 700
        self.on_tick()
        a.HCInFlight = False
        a.HCDirty = False
        self.clock[0] = 50
        self.on_tick()
        line = [entry for entry in self.logs if entry.startswith("[HC Save]")]
        self.assertEqual(1, len(line), self.logs)
        self.assertIn("job=World stages=1 max_stage_ticks=50 total_ticks=50 slowest_stage=1", line[0])

    def test_save_line_prints_only_for_a_new_slowest_stage_per_job(self):
        done = self.consts["STEP_DONE"]
        a = FakeJob("Scenes", [done, done, done], self.env)
        self.env["s_Jobs"].Insert(a)
        for ticks in (500, 300, 800):
            a.HCDirty = True
            a.HCDue = 0.0
            self.clock[0] = ticks
            self.on_tick()
        line = [entry for entry in self.logs if entry.startswith("[HC Save]")]
        self.assertEqual(2, len(line), self.logs)
        self.assertIn("max_stage_ticks=500", line[0])
        self.assertIn("max_stage_ticks=800", line[1])

    def test_default_job_step_is_the_unchanged_single_whole_write(self):
        text = WORKBUDGET.read_text()
        step = translated(text, "HCStep", dict(self.consts), "HCSaveJob")
        job = N(HCWrite=lambda: True)
        self.assertEqual(self.consts["STEP_DONE"], step(job))
        job = N(HCWrite=lambda: False)
        self.assertEqual(self.consts["STEP_FAILED"], step(job))

    def test_single_step_job_behaves_exactly_like_the_old_whole_store_flush(self):
        done = self.consts["STEP_DONE"]
        a = FakeJob("Scenes", [done], self.env)
        self.env["s_Jobs"].Insert(a)
        self.on_tick()
        self.assertEqual((1, False, False, 160.0), (a.calls, a.HCInFlight, a.HCDirty, a.HCDue))

    def test_not_due_or_clean_jobs_are_never_stepped(self):
        done = self.consts["STEP_DONE"]
        due_later = FakeJob("World", [done], self.env)
        due_later.HCDue = 500.0
        clean = FakeJob("Scenes", [done], self.env)
        clean.HCDirty = False
        self.env["s_Jobs"].Insert(due_later)
        self.env["s_Jobs"].Insert(clean)
        self.on_tick()
        self.assertEqual((0, 0), (due_later.calls, clean.calls))


class FakeDisk:
    """SYNTHETIC file system with an operation log; the store's JSON ports are fakes."""

    def __init__(self, files):
        self.files = dict(files)
        self.ops = []

    def exist(self, path):
        return path in self.files

    def read(self, path):
        self.ops.append(("read", path))
        return self.files.get(path, "")

    def write(self, path, text):
        self.ops.append(("write", path))
        self.files[path] = text
        return True

    def delete(self, path):
        self.ops.append(("delete", path))
        return self.files.pop(path, None) is not None

    def copy(self, source, target):
        self.ops.append(("copy", source + ">" + target))
        if source not in self.files:
            return False
        self.files[target] = self.files[source]
        return True


class WorldStoreStagedSaveTests(unittest.TestCase):
    PATH = "$profile:HollowCountry/world.json"
    TEMP = PATH + ".tmp"
    BACKUP = PATH + ".bak"

    def setUp(self):
        self.consts = constants(WORKBUDGET.read_text())
        self.disk = FakeDisk({self.PATH: "old-image"})
        self.encoded = []
        self.data = N(version=1)
        text = STORE.read_text()
        self.store_consts = constants(text)
        self.env = dict(
            len=len, str=str, Print=lambda s: None,
            HCSaveJob=N(**self.consts), FileExist=self.disk.exist, DeleteFile=self.disk.delete,
            CopyFile=self.disk.copy, MAX_BYTES=1048576,
            HCWorldData=N(Valid=lambda d: d is not None and getattr(d, "valid", True)),
        )
        self.store = N(
            m_Path=self.PATH, m_Temp=self.TEMP, m_Backup=self.BACKUP, m_Fresh=False, m_KeepBackup=False,
            m_Fault=False, m_VerifiedText="old-image", m_SaveStage=0, m_PendText="", m_PendPrior="",
        )
        self.store.Read = self.disk.read
        self.store.Write = self.disk.write
        self.store.Encode = lambda d: "new-image-v%d" % d.version
        self.store.Fault = lambda: setattr(self.store, "m_Fault", True) or False
        self.step_fn = translated(text, "SaveStep", self.env, "HCWorldStore")
        self.save_fn = translated(text, "Save", self.env, "HCWorldStore")
        failed = translated(text, "SaveFailed", self.env, "HCWorldStore")
        self.store.SaveFailed = lambda: failed(self.store)
        self.store.SaveStep = lambda d: self.step_fn(self.store, d)
        self.store.SaveInFlight = lambda: self.store.m_SaveStage != 0
        self.step = lambda: self.store.SaveStep(self.data)

    def test_serialize_and_prior_compare_stages_never_touch_disk_writes(self):
        more = self.consts["STEP_MORE"]
        self.assertEqual(more, self.step())
        self.assertEqual([], self.disk.ops)
        self.assertTrue(self.store.SaveInFlight())
        self.assertEqual(more, self.step())
        self.assertEqual([("read", self.PATH)], self.disk.ops)
        self.assertEqual({self.PATH: "old-image"}, self.disk.files)

    def test_commit_runs_in_one_tick_in_the_original_order_and_clears_the_intent(self):
        self.step()
        self.step()
        self.disk.ops.clear()
        self.assertEqual(self.consts["STEP_DONE"], self.step())
        # HCWorldStore.Write does its own readback (not modelled by the fake), so no read op for it.
        self.assertEqual(
            [("write", self.TEMP), ("copy", self.PATH + ">" + self.BACKUP), ("read", self.BACKUP),
             ("delete", self.PATH), ("copy", self.TEMP + ">" + self.PATH), ("read", self.PATH), ("delete", self.TEMP)],
            self.disk.ops)
        self.assertEqual({self.PATH: "new-image-v1", self.BACKUP: "old-image"}, self.disk.files)
        self.assertFalse(self.store.SaveInFlight())
        self.assertEqual("new-image-v1", self.store.m_VerifiedText)

    def test_the_snapshot_is_taken_at_the_first_stage_not_at_commit(self):
        self.step()
        self.data.version = 2
        self.step()
        self.step()
        self.assertEqual("new-image-v1", self.disk.files[self.PATH])

    def test_external_edit_refusal_fails_the_second_stage_before_any_write(self):
        self.disk.files[self.PATH] = "edited-by-hand"
        self.step()
        self.assertEqual(self.consts["STEP_FAILED"], self.step())
        self.assertTrue(self.store.m_Fault)
        self.assertFalse(self.store.SaveInFlight())
        self.assertEqual([("read", self.PATH)], self.disk.ops)
        self.assertEqual({self.PATH: "edited-by-hand"}, self.disk.files)

    def test_invalid_data_or_failed_encode_fails_the_first_stage(self):
        self.data.valid = False
        self.assertEqual(self.consts["STEP_FAILED"], self.step())
        self.assertTrue(self.store.m_Fault)
        self.assertEqual([], self.disk.ops)

    def test_faulted_store_refuses_every_stage(self):
        self.store.m_Fault = True
        self.assertEqual(self.consts["STEP_FAILED"], self.step())
        self.assertEqual([], self.disk.ops)

    def test_fresh_world_skips_the_prior_read_and_backup(self):
        self.store.m_Fresh = True
        self.disk.files.pop(self.PATH)
        self.step()
        self.step()
        self.assertEqual([], self.disk.ops)
        self.assertEqual(self.consts["STEP_DONE"], self.step())
        self.assertEqual({self.PATH: "new-image-v1"}, self.disk.files)

    def test_synchronous_save_is_the_same_three_stages_and_ends_with_identical_files(self):
        self.store.SaveStep = lambda d: self.step_fn(self.store, d)
        self.assertTrue(self.save_fn(self.store, self.data))
        self.assertEqual({self.PATH: "new-image-v1", self.BACKUP: "old-image"}, self.disk.files)
        self.assertFalse(self.store.SaveInFlight())
        # A second synchronous save starts from stage 0 again.
        self.data.version = 2
        self.assertTrue(self.save_fn(self.store, self.data))
        self.assertEqual({self.PATH: "new-image-v2", self.BACKUP: "new-image-v1"}, self.disk.files)

    def test_synchronous_save_reports_a_faulted_store_as_false(self):
        self.store.m_Fault = True
        self.assertFalse(self.save_fn(self.store, self.data))


class StepTimerTests(unittest.TestCase):
    """SYNTHETIC raw tick values supplied by the test: the timer never reads a clock itself."""

    METHODS = ("HCDefine", "HCAdd", "HCItem", "HCDeferred", "HCEndTick", "HCCloseWindow", "HCLine")

    def setUp(self):
        self.logs = []
        text = STEP_TIMER.read_text()
        self.consts = constants(text)
        env = dict(EArray=EArray, len=len, str=str, Print=self.logs.append, **self.consts)
        self.timer = N(m_Owner="Interiors", m_Names=EArray(), m_Current=EArray(), m_Worst=EArray(),
                       m_CurrentItems=0, m_WorstTotal=0, m_WorstItems=0, m_ItemMax=0, m_ItemType="",
                       m_DeferredCount=0, m_DeferredMax=0, m_Ticks=0, m_Window=0, m_Peak=0, m_Work=False)
        import functools
        for name in self.METHODS:
            setattr(self.timer, name, functools.partial(translated(text, name, env, "HCStepTimer"), self.timer))
        self.steps = [self.timer.HCDefine(name) for name in ("resolve", "inspect", "create")]

    def lines(self):
        return [line for line in self.logs if line.startswith("[HC Step]")]

    def test_one_line_per_window_reports_the_worst_tick_split_by_step(self):
        resolve, inspect, create = self.steps
        self.assertEqual([0, 1, 2], self.steps)
        window = self.consts["WINDOW_TICKS"]
        for tick in range(window):
            if tick == 7:
                self.timer.HCAdd(resolve, 3000)
                self.timer.HCAdd(inspect, 2000)
                self.timer.HCAdd(create, 400000)
                self.timer.HCItem("Land_House_1W01:case_a", 405000)
                self.timer.HCEndTick(410000)
            elif tick == 9:
                self.timer.HCAdd(create, 20000)
                self.timer.HCItem("Land_House_1W02:chair", 21000)
                self.timer.HCEndTick(22000)
            else:
                self.timer.HCEndTick(100)
            if tick < window - 1:
                self.assertEqual([], self.lines())
        # A deferred callback after the window closed belongs to the next window.
        self.timer.HCDeferred(250000)
        lines = self.lines()
        self.assertEqual(1, len(self.logs), self.logs)
        line = self.logs[0]
        for part in ("[HC Step] owner=Interiors window=1 ticks=60 worst_tick_ticks=410000 worst_tick_items=1",
                     " resolve=3000 inspect=2000 create=400000 other=5000",
                     " heaviest_item_ticks=405000 heaviest=Land_House_1W01:case_a",
                     " deferred_n=0 deferred_max_ticks=0", "; raw TickCount units; runtime acceptance pending"):
            self.assertIn(part, line)
        self.assertEqual([], lines[1:])

    def test_idle_windows_stay_silent_unless_the_worst_tick_is_a_new_peak(self):
        resolve = self.steps[0]
        window = self.consts["WINDOW_TICKS"]
        for _ in range(window):
            self.timer.HCEndTick(100)
        self.assertEqual(1, len(self.lines()), "the first window sets the peak")
        for _ in range(window):
            self.timer.HCEndTick(90)
        self.assertEqual(1, len(self.lines()), "an idle window below the peak prints nothing")
        for tick in range(window):
            if tick == 3:
                self.timer.HCAdd(resolve, 900)
            self.timer.HCEndTick(1000 if tick == 3 else 10)
        self.assertEqual(2, len(self.lines()), "maintenance-only peak is reported")
        self.assertIn("window=3", self.lines()[1])
        self.assertIn("worst_tick_items=0", self.lines()[1])

    def test_out_of_tick_work_counts_as_window_work_and_reports_count_and_max(self):
        window = self.consts["WINDOW_TICKS"]
        for _ in range(window):
            self.timer.HCEndTick(500)
        self.timer.HCDeferred(30000)
        self.timer.HCDeferred(90000)
        self.timer.HCDeferred(-4)
        for _ in range(window):
            self.timer.HCEndTick(10)
        self.assertEqual(2, len(self.lines()), self.logs)
        self.assertIn(" deferred_n=2 deferred_max_ticks=90000", self.lines()[1])

    def test_steps_are_bounded_and_out_of_range_indices_are_ignored(self):
        for index in range(20):
            self.timer.HCDefine("s" + str(index))
        self.assertEqual(self.consts["MAX_STEPS"], self.timer.m_Names.Count())
        self.assertEqual(-1, self.timer.HCDefine("late"))
        self.timer.HCAdd(-1, 5)
        self.timer.HCAdd(99, 5)
        self.assertEqual([0] * self.consts["MAX_STEPS"], list(self.timer.m_Current))

    def test_timer_reads_no_clock_and_allocates_only_at_construction(self):
        text = re.sub(r"//[^\n]*", "", STEP_TIMER.read_text())
        for forbidden in ("GetGame", "GetTickTime", "TickCount("):
            self.assertNotIn(forbidden, text, forbidden)
        self.assertEqual(3, text.count("new array<"), "only the three step arrays are allocated")
        self.assertLessEqual(self.consts["MAX_STEPS"], 8)


class FurnishMeasuredChargeTests(unittest.TestCase):
    """SYNTHETIC cursor items with scripted raw tick costs drive the module's furnish loop."""

    def run_tick(self, costs, slot=True):
        text = INTERIOR_MODULE.read_text()
        module_consts = constants(text)
        cursor_consts = constants(INTERIOR_CURSOR.read_text())
        clock = [0]
        items = []
        steps = N(HCItem=lambda kind, ticks: items.append((kind, ticks)))
        queue = list(costs)

        class Cursor:
            def HCComplete(self):
                return not queue

            def HCTick(self, module, settings, placed):
                clock[0] = queue.pop(0)

            def HCLastCost(self):
                return cursor_consts["SLOT_UNITS"] if slot else cursor_consts["CHEAP_UNITS"]

        owner = N(m_FurnishWork=Cursor(), m_FurnishUnits=unit_budget(), m_Objects=EArray())
        env = dict(module_consts, len=len, str=str, TickCount=lambda prev: clock[0],
                   HCInteriorPlacementCursor=N(**cursor_consts),
                   HCInteriorTemplatePlacement=N(HCLastType=lambda: "Land_House_1W01:case_a"),
                   HCInteriorTemplates=N(Loaded=lambda: True))
        translated(text, "HCFurnish", env, "HCInteriorsModule", integer_division=True)(owner, N(), steps)
        return len(costs) - len(queue), items, module_consts

    def test_heavy_creation_attempt_ends_the_tick_after_one_item(self):
        # 45 ms per attempt at the measured 10000 ticks/ms (boot 028 ticks_per_ms=10000).
        ran, items, _ = self.run_tick([450000, 450000, 450000])
        self.assertEqual(1, ran)
        self.assertEqual([("Land_House_1W01:case_a", 450000)], items)

    def test_cheap_creation_attempts_keep_the_declared_three_per_tick(self):
        ran, items, _ = self.run_tick([20000] * 6)
        self.assertEqual(3, ran)
        self.assertEqual(3, len(items))

    def test_mid_cost_attempts_stop_once_the_measured_units_are_spent(self):
        ran, _, consts = self.run_tick([60000] * 6)   # 15 units each against 24
        self.assertEqual(2, ran)

    def test_cheap_deferrals_are_not_reported_as_items_and_keep_their_count(self):
        ran, items, consts = self.run_tick([10] * 40, slot=False)
        self.assertEqual(consts["FURNISH_UNITS_PER_TICK"], ran)
        self.assertEqual([], items)


class SceneStoreStagedSaveTests(unittest.TestCase):
    PATH = "$profile:HollowCountry/scene-chains.json"
    TEMP = PATH + ".tmp"
    BACKUP = PATH + ".bak"

    def setUp(self):
        self.consts = constants(WORKBUDGET.read_text())
        self.disk = FakeDisk({self.PATH: "image-r4"})
        self.faults = []
        text = SCENE_CHAINS.read_text()
        self.state = N(Revision=4, valid=True)

        def write_new(path, data, limit):
            if path in self.disk.files or not (0 < len(data) <= limit):
                return False
            self.disk.write(path, data)
            self.disk.read(path)
            return True
        self.env = dict(
            len=len, str=str, Print=lambda s: None,
            HCSaveJob=N(**self.consts), FileExist=self.disk.exist, DeleteFile=self.disk.delete,
            CopyFile=self.disk.copy, HCGroupIO=N(WriteNew=write_new),
            HCSceneChains=N(StateValid=lambda s: s is not None and s.valid),
        )
        self.store = N(m_Path=self.PATH, m_Fault=False, m_Image="image-r4", m_Revision=4,
                       m_SaveStage=0, m_PendText="", m_PendRevision=0)
        self.store.ReadImage = self.disk.read
        self.store.Encode = lambda s: "image-r%d" % s.Revision

        def fault():
            self.faults.append(1)
            self.store.m_Fault = True
            return False
        self.store.Fault = fault
        self.step_fn = translated(text, "SaveStep", self.env, "HCSceneChainStore")
        self.save_fn = translated(text, "Save", self.env, "HCSceneChainStore")
        failed = translated(text, "SaveFailed", self.env, "HCSceneChainStore")
        in_flight = translated(text, "SaveInFlight", self.env, "HCSceneChainStore")
        self.store.SaveFailed = lambda: failed(self.store)
        self.store.SaveStep = lambda s: self.step_fn(self.store, s)
        self.store.SaveInFlight = lambda: in_flight(self.store)
        self.step = lambda: self.store.SaveStep(self.state)

    def test_serialize_and_prior_compare_stages_never_write(self):
        more = self.consts["STEP_MORE"]
        self.assertEqual(more, self.step())
        self.assertEqual([], self.disk.ops)
        self.assertTrue(self.store.SaveInFlight())
        self.assertEqual(4, self.state.Revision, "the live state keeps the stored revision between stages")
        self.assertEqual(more, self.step())
        self.assertEqual([("read", self.PATH)], self.disk.ops)
        self.assertEqual({self.PATH: "image-r4"}, self.disk.files)

    def test_backup_refresh_is_its_own_stage_and_leaves_no_intent(self):
        self.step()
        self.step()
        self.disk.ops.clear()
        self.assertEqual(self.consts["STEP_MORE"], self.step())
        self.assertEqual([("copy", self.PATH + ">" + self.BACKUP), ("read", self.BACKUP)], self.disk.ops)
        self.assertEqual({self.PATH: "image-r4", self.BACKUP: "image-r4"}, self.disk.files)
        self.assertNotIn(self.TEMP, self.disk.files)
        self.assertFalse(self.store.m_Fault)

    def test_commit_writes_intent_replaces_reads_back_and_clears_the_intent_in_one_stage(self):
        for _ in range(3):
            self.step()
        self.disk.ops.clear()
        self.assertEqual(self.consts["STEP_DONE"], self.step())
        self.assertEqual(
            [("write", self.TEMP), ("read", self.TEMP), ("delete", self.PATH), ("copy", self.TEMP + ">" + self.PATH),
             ("read", self.PATH), ("delete", self.TEMP)], self.disk.ops)
        self.assertEqual({self.PATH: "image-r5", self.BACKUP: "image-r4"}, self.disk.files)
        self.assertEqual((5, 5, "image-r5", False), (self.state.Revision, self.store.m_Revision, self.store.m_Image, self.store.m_Fault))
        self.assertFalse(self.store.SaveInFlight())

    def test_synchronous_save_runs_the_same_stages_and_ends_with_the_original_files(self):
        self.assertTrue(self.save_fn(self.store, self.state))
        self.assertEqual({self.PATH: "image-r5", self.BACKUP: "image-r4"}, self.disk.files)
        self.assertTrue(self.save_fn(self.store, self.state))
        self.assertEqual({self.PATH: "image-r6", self.BACKUP: "image-r5"}, self.disk.files)
        self.assertEqual([], self.faults)

    def test_a_synchronous_barrier_save_mid_flight_restarts_from_a_fresh_snapshot(self):
        self.step()
        self.step()
        self.assertTrue(self.save_fn(self.store, self.state))
        self.assertFalse(self.store.SaveInFlight())
        self.assertEqual({self.PATH: "image-r5", self.BACKUP: "image-r4"}, self.disk.files)

    def test_fresh_store_without_a_current_image_skips_prior_and_backup(self):
        self.disk.files.clear()
        self.store.m_Image = ""
        self.assertEqual(self.consts["STEP_MORE"], self.step())
        self.assertEqual(self.consts["STEP_MORE"], self.step())
        self.assertEqual(self.consts["STEP_MORE"], self.step())
        self.assertEqual([], self.disk.ops)
        self.assertEqual(self.consts["STEP_DONE"], self.step())
        self.assertEqual({self.PATH: "image-r5"}, self.disk.files)

    def test_external_edit_faults_before_any_write_and_preserves_the_files(self):
        self.disk.files[self.PATH] = "edited-by-hand"
        self.step()
        self.assertEqual(self.consts["STEP_FAILED"], self.step())
        self.assertEqual(([1], True), (self.faults, self.store.m_Fault))
        self.assertFalse(self.store.SaveInFlight())
        self.assertEqual({self.PATH: "edited-by-hand"}, self.disk.files)
        self.assertEqual(self.consts["STEP_FAILED"], self.step(), "a faulted store refuses every stage")

    def test_a_surviving_intent_faults_the_commit_and_keeps_recovery_files(self):
        for _ in range(3):
            self.step()
        self.disk.files[self.TEMP] = "stale-intent"
        self.assertEqual(self.consts["STEP_FAILED"], self.step())
        self.assertTrue(self.store.m_Fault)
        self.assertEqual({self.PATH: "image-r4", self.BACKUP: "image-r4", self.TEMP: "stale-intent"}, self.disk.files)
        self.assertEqual((4, "image-r4"), (self.store.m_Revision, self.store.m_Image))

    def test_invalid_state_revision_mismatch_and_faulted_store_refuse_without_io(self):
        self.state.Revision = 3
        self.assertEqual(self.consts["STEP_FAILED"], self.step())
        self.assertEqual([], self.disk.ops)
        self.assertFalse(self.save_fn(self.store, self.state))
        self.assertEqual(2, len(self.faults), "a faulted synchronous save still prints the refusal")


class SourceContractTests(unittest.TestCase):
    def source(self, path):
        return re.sub(r"//[^\n]*", "", path.read_text())

    def test_store_serializes_through_one_encode_helper_and_commits_in_a_single_stage(self):
        text = self.source(STORE)
        self.assertIn("int SaveStep(HCWorldData data)", text)
        commit = text.split("string text = m_PendText;")[1].split("return HCSaveJob.STEP_DONE")[0]
        for call in ("Write(m_Temp", "CopyFile(m_Path, m_Backup)", "DeleteFile(m_Path)", "CopyFile(m_Temp, m_Path)", "DeleteFile(m_Temp)"):
            self.assertIn(call, commit)
        early = text.split("string text = m_PendText;")[0].split("int SaveStep(")[1]
        for call in ("Write(", "CopyFile(", "DeleteFile("):
            self.assertNotIn(call, early, "the durability intent must not be written before the commit stage")

    def test_world_module_snapshots_then_clears_dirty_and_restores_it_on_failure(self):
        text = self.source(WORLD_MODULE)
        self.assertIn("override int HCStep()", text)
        self.assertIn("HCStepRoutine()", text)
        body = text.split("int HCStepRoutine()")[1].split("\n    }\n")[0]
        self.assertIn("m_Dirty = false", body)
        self.assertIn("m_Dirty = true", body)
        self.assertIn("HCInFlight", text.split("override void OnStop()")[1].split("bool HCFlushRoutine")[0])

    def test_interior_furnishing_uses_the_shared_unit_budget_not_the_clock_guard(self):
        module = self.source(INTERIOR_MODULE)
        self.assertIn("HCUnitBudget", module)
        self.assertIn("FURNISH_UNITS_PER_TICK", module)
        self.assertNotIn("m_FurnishBudget", module)
        self.assertNotIn("HCContinue", module)
        cursor = self.source(INTERIOR_CURSOR)
        self.assertIn("int HCLastCost()", cursor)
        self.assertIn("SLOT_UNITS", cursor)

    def test_interior_slot_cost_exceeds_cheap_cost_and_a_tick_admits_several_but_bounded_slots(self):
        cursor_consts = constants(self.source(INTERIOR_CURSOR))
        module_consts = constants(self.source(INTERIOR_MODULE))
        self.assertGreater(cursor_consts["SLOT_UNITS"], cursor_consts["CHEAP_UNITS"])
        slots_per_tick = module_consts["FURNISH_UNITS_PER_TICK"] // cursor_consts["SLOT_UNITS"]
        self.assertGreaterEqual(slots_per_tick, 2)
        self.assertLessEqual(slots_per_tick, 4)

    def test_interior_load_time_is_logged_in_raw_ticks_once(self):
        text = self.source(INTERIOR_TEMPLATES)
        self.assertEqual(1, text.count("load_ticks="))
        self.assertIn("TickCount(loadStart)", text)
        self.assertIn("load_ticks=\" + loadTicks.ToString()", text)

    def test_scene_save_job_is_staged_and_clears_in_flight_before_stopping(self):
        module = self.source(SCENES_MODULE)
        job = module.split("class HCSceneSaveJob")[1]
        self.assertIn("override int HCStep()", job)
        self.assertIn("HCStepRoutine()", job)
        routine = module.split("int HCStepRoutine()")[1].split("\n    }\n")[0]
        self.assertIn("m_Store.SaveStep(m_State)", routine)
        self.assertLess(routine.index("HCInFlight = false"), routine.index("OnStop()"))
        commit = module.split("bool Commit(int now)")[1].split("\n    }\n")[0]
        self.assertIn("SaveBarrierDone()", commit)
        barrier = module.split("void SaveBarrierDone()")[1].split("\n    }\n")[0]
        self.assertIn("m_SaveJob.HCInFlight = false", barrier)
        self.assertIn("m_SaveJob.HCDirty = false", barrier)
        stop = module.split("override void OnStop()")[1].split("\n    }\n")[0]
        self.assertIn("SaveAbandon()", stop)
        self.assertLess(stop.index("SaveAbandon()"), stop.index("HCFlush(m_SaveJob)"))
        store = self.source(SCENE_CHAINS)
        commit_stage = store.split("string text = m_PendText;")[1].split("return HCSaveJob.STEP_DONE")[0]
        for call in ("WriteNew(m_Path + \".tmp\"", "DeleteFile(m_Path)", "CopyFile(m_Path + \".tmp\", m_Path)", "DeleteFile(m_Path + \".tmp\")"):
            self.assertIn(call, commit_stage)
        early = store.split("string text = m_PendText;")[0].split("int SaveStep(")[1]
        self.assertNotIn(".tmp", early, "the durability intent must not be written before the commit stage")

    def test_interiors_tick_is_sub_timed_and_measured_charge_is_used(self):
        module = self.source(INTERIOR_MODULE)
        self.assertIn("HCChargeMeasured(", module)
        self.assertIn("FURNISH_TICKS_PER_UNIT", module)
        self.assertIn("HCEndTick(TickCount(", module)
        placement = self.source(INTERIOR_PLACEMENT)
        self.assertIn("CallLater(HCInteriorTemplatePlacement.HCTimedPathgraph, 100, false, placedObject)", placement)
        timed = placement.split("static void HCTimedPathgraph(Object")[1].split("\n    }\n")[0]
        self.assertIn("GetGame().UpdatePathgraphRegionByObject(", timed)
        self.assertIn("[HC Step]", self.source(STEP_TIMER))

    def test_core_helper_is_the_only_new_budget_type_and_is_reused_three_times(self):
        for path in (SCRIPTS / "4_World/Ecology/HCEcologyRuntime.c", INTERIOR_MODULE):
            self.assertIn("HCUnitBudget", path.read_text(), path.name)
        self.assertIn("HCSaveJob", self.source(WORKBUDGET))


if __name__ == "__main__":
    unittest.main()
