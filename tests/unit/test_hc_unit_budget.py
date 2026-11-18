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

RENAMES = ("HCSaveJob", "HCWorldData", "HCUnitBudget")


def translated(text, name, env, owner, member=True):
    """Syntax-only translation of one authored method (types that the translator does not know
    about are renamed to the HCEvent prefix it strips)."""
    renamed = text
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
    for name in ("HCReset", "HCTake", "HCCharge", "HCExhausted", "HCUsed", "HCLimit", "HCItems"):
        setattr(budget, name, functools.partial(translated(text, name, {}, "HCUnitBudget"), budget))
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
        self.sched = N(m_Next=0, m_Active=None, m_StageTicks=0, m_StageMax=0, m_Stages=0, m_TotalTicks=0)
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
        self.assertNotIn("[HC Perf]", line[0])

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

    def test_core_helper_is_the_only_new_budget_type_and_is_reused_three_times(self):
        for path in (SCRIPTS / "4_World/Ecology/HCEcologyRuntime.c", INTERIOR_MODULE):
            self.assertIn("HCUnitBudget", path.read_text(), path.name)
        self.assertIn("HCSaveJob", self.source(WORKBUDGET))


if __name__ == "__main__":
    unittest.main()
