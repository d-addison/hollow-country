"""Runner, driver registry and discovery tests. Synthetic: they never establish DayZ behaviour.

Expectations derive from the catalog, the capability inventory and the driver registry.
"""
import json
from pathlib import Path
import sys
import tempfile
import unittest

from tools.testing import automation, discovery, drivers
from tools.validate import automation_drift, bdd

ROOT = Path(__file__).resolve().parents[2]
CATALOG = automation.load_catalog(ROOT / "tests/catalog.json")
ALL_CAPABILITIES = {name: "available" for name in discovery.capability_names(ROOT)}


def python_driver(driver_id, code, *, kind="offline", needs=(), judge=drivers.judge_exit, timeout=30):
    return drivers.Driver(driver_id, kind, "synthetic", needs,
                          lambda root, inputs: [sys.executable, "-c", code], judge, timeout=timeout)


def run(tasks, registry, directory, **kwargs):
    manifest = {"schema_version": 1, "run_id": "synthetic", "tasks": tasks}
    return automation.run_automation(manifest, Path(directory) / "out", registry=registry, **kwargs)


class RunnerTests(unittest.TestCase):
    def setUp(self):
        self.scratch = tempfile.TemporaryDirectory()
        self.addCleanup(self.scratch.cleanup)
        self.dir = Path(self.scratch.name)
        self.sentinel = self.dir / "launched"
        touch = f"open({str(self.sentinel)!r}, 'w').close(); print('ran')"
        self.registry = {d.id: d for d in (
            python_driver("t.pass", "print('ok')"),
            python_driver("t.silent", "pass"),
            python_driver("t.fail", "import sys; sys.exit(1)"),
            python_driver("t.slow", "import time; time.sleep(30)", timeout=1),
            python_driver("t.needs", touch, needs=("secret_scan",)),
            python_driver("t.native", touch, kind="native"),
        )}

    def result(self, report, task):
        return next(t for t in report["tasks"] if t["task"] == task)

    def test_every_catalog_row_gets_one_valid_outcome_and_originals_are_listed(self):
        report = run([], self.registry, self.dir, capabilities=ALL_CAPABILITIES)
        self.assertEqual([r["id"] for r in report["tests"]], [r["id"] for r in CATALOG["tests"]])
        self.assertTrue(all(r["outcome"] in drivers.OUTCOMES for r in report["tests"]))
        original = report["coverage"]["original"]
        self.assertEqual(original["listed"], original["expected"])
        self.assertEqual({r["id"] for r in original["rows"]}, set(automation.ORIGINAL_IDS))
        self.assertEqual(sum(report["counts"].values()), len(CATALOG["tests"]))
        self.assertEqual(report["acceptance"], "not_evaluated")
        self.assertNotIn("multiplayer", report["evidence_label"])
        self.assertEqual(report["clients"], 0)

    def test_deferred_rows_and_tasks_are_notrun_with_the_owner_reason(self):
        report = run([], self.registry, self.dir, capabilities=ALL_CAPABILITIES)
        deferred = set(discovery.DEFERRED_CAPABILITIES)
        for source, row in zip(CATALOG["tests"], report["tests"]):
            if set(source["requires"]) & deferred:
                self.assertEqual((row["outcome"], row["reason"]), ("NOTRUN", automation.DEFERRED_REASON))
        for task in automation.DEFERRED_TASKS:
            found = self.result(report, task)
            self.assertEqual((found["outcome"], found["reason"]), ("NOTRUN", automation.DEFERRED_REASON))

    def test_native_driver_is_notrun_unless_listed_in_trusted_drivers(self):
        report = run([{"id": "n1", "driver": "t.native"}], self.registry, self.dir,
                     capabilities=ALL_CAPABILITIES)
        found = self.result(report, "n1")
        self.assertEqual((found["outcome"], found["reason"]), ("NOTRUN", "untrusted_native"))
        self.assertFalse(self.sentinel.exists())

    def test_trusted_native_driver_runs_and_registered_native_drivers_are_gated(self):
        report = run([{"id": "n1", "driver": "t.native"}], self.registry, self.dir,
                     capabilities=ALL_CAPABILITIES, trusted_drivers=["t.native"])
        self.assertEqual(self.result(report, "n1")["outcome"], "PASS")
        self.assertTrue(self.sentinel.exists())
        for driver in drivers.DRIVERS.values():
            self.assertEqual(driver.trust, "explicit" if driver.kind == "native" else "builtin")
        self.assertTrue(any(d.kind == "native" for d in drivers.DRIVERS.values()))

    def test_missing_capability_blocks_without_launching(self):
        caps = dict(ALL_CAPABILITIES, secret_scan="unknown")
        report = run([{"id": "c1", "driver": "t.needs"}], self.registry, self.dir, capabilities=caps)
        found = self.result(report, "c1")
        self.assertEqual((found["outcome"], found["reason"]), ("BLOCKED", "missing_capability:secret_scan"))
        self.assertFalse(self.sentinel.exists())

    def test_zero_exit_without_terminal_result_and_failures_are_not_pass(self):
        report = run([{"id": "s", "driver": "t.silent"}, {"id": "f", "driver": "t.fail"},
                      {"id": "p", "driver": "t.pass"}], self.registry, self.dir,
                     capabilities=ALL_CAPABILITIES)
        self.assertEqual((self.result(report, "s")["outcome"], self.result(report, "s")["reason"]),
                         ("FAIL", "no_terminal_result"))
        self.assertEqual(self.result(report, "f")["outcome"], "FAIL")
        self.assertEqual(self.result(report, "p")["outcome"], "PASS")
        self.assertEqual(report["status"], "FAIL")

    def test_timeout_is_fail_and_every_record_is_valid_evidence(self):
        report = run([{"id": "t", "driver": "t.slow"}], self.registry, self.dir, capabilities=ALL_CAPABILITIES)
        self.assertEqual(self.result(report, "t")["reason"], "timeout")
        for task in report["tasks"]:
            self.assertTrue(task["evidence"]["valid"], task)
            record = json.loads((self.dir / "out" / task["evidence"]["path"]).read_text())
            self.assertNotIn("client_count", record)
            self.assertNotIn("multiplayer", json.dumps(record).replace("never multiplayer", ""))

    def test_passing_task_supports_but_never_accepts_an_original_id(self):
        covered = sorted(automation.ORIGINAL_IDS)
        report = run([{"id": "p", "driver": "t.pass", "covers": covered}], self.registry, self.dir,
                     capabilities=ALL_CAPABILITIES)
        for row in report["coverage"]["original"]["rows"]:
            self.assertNotEqual(row["outcome"], "PASS")
        self.assertTrue(any("p" in row["supporting_tasks"] for row in report["tests"]))

    def test_manifest_cannot_choose_commands_or_reuse_output(self):
        for task in ({"id": "x", "driver": "sh -c true"}, {"id": "x", "driver": "t.pass", "argv": ["sh"]},
                     {"id": "x", "driver": "t.pass", "inputs": {"shell": "true"}},
                     {"id": "x", "driver": "t.pass", "covers": ["NOPE-000"]},
                     {"id": next(iter(automation.DEFERRED_TASKS)), "driver": "t.pass"}):
            with self.subTest(task=task), self.assertRaises(ValueError):
                run([task], self.registry, self.dir, capabilities=ALL_CAPABILITIES)
            self.assertFalse((self.dir / "out").exists())
        with self.assertRaises(ValueError):
            run([], self.registry, self.dir, capabilities=ALL_CAPABILITIES, trusted_drivers=["unknown.driver"])
        (self.dir / "out").mkdir()
        (self.dir / "out/old").write_text("x")
        with self.assertRaises(ValueError):
            run([], self.registry, self.dir, capabilities=ALL_CAPABILITIES)

    def test_judges_never_pass_skipped_or_empty_results(self):
        self.assertEqual(drivers.judge_exit(0, "")[0], "FAIL")
        self.assertEqual(drivers.judge_exit(drivers.SKIPPED_CODES[0], "x")[0], "BLOCKED")
        self.assertEqual(drivers.judge_bdd_offline(0, "Bound offline scenarios: 0; runtime acceptance: NOT EXECUTED")[0], "FAIL")
        self.assertEqual(drivers.judge_bdd_runtime(0, json.dumps({"intact": True}))[0], "BLOCKED")
        self.assertEqual(drivers.judge_compile_gate(0, "compile_gate: Mission load not observed")[0], "FAIL")


class DiscoveryTests(unittest.TestCase):
    def test_inventory_covers_every_required_capability_with_evidence(self):
        report = discovery.inventory(ROOT)
        required = {name for row in CATALOG["tests"] for name in row["requires"]}
        self.assertEqual(set(report["capabilities"]), required)
        for fact in report["capabilities"].values():
            self.assertIn(fact["status"], discovery.STATUSES)
            self.assertTrue(fact["evidence"])
        self.assertFalse(report["machine_discovery_performed"])

    def test_installed_paths_never_grant_deferred_or_client_capabilities(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            for name in ("DayZ_x64.exe", "DayZDiag_x64.exe", "DayZServer_x64.exe"):
                (base / name).write_text("")
            machine = discovery.discover_machine({"client": base, "server": base})
            self.assertEqual(machine["facts"]["server"]["status"], "known")
            report = discovery.inventory(ROOT, machine)
        self.assertTrue(report["machine_discovery_performed"])
        for name in discovery.DEFERRED_CAPABILITIES:
            if name in report["capabilities"]:
                self.assertEqual(report["capabilities"][name]["status"], "unverified")
        self.assertEqual(report["capabilities"]["normal_server"]["status"], "known")
        self.assertEqual(discovery.planner_capabilities(report)["licensed_authenticated_rendered_client"], "unknown")

    def test_absent_tools_are_absent_and_evidence_has_no_home_path(self):
        machine = discovery.discover_machine({"client": "/nonexistent/hc", "server": "/nonexistent/hc"})
        self.assertEqual(machine["facts"]["diag"]["status"], "absent")
        text = json.dumps(machine) + json.dumps(discovery.inventory(ROOT, machine))
        self.assertNotIn(str(Path.home()), text)
        self.assertEqual(discovery.redact(f"{Path.home()}/x"), "~/x")

    def test_checked_in_capabilities_match_the_repository_inventory(self):
        self.assertEqual(json.loads((ROOT / "tests/capabilities.json").read_text()),
                         discovery.capabilities_document(ROOT))


class RuntimeBindingTests(unittest.TestCase):
    def test_runtime_scenarios_match_bindings_and_stay_blocked(self):
        report = bdd.runtime_report((ROOT / "tests/features/runtime.feature").read_text())
        self.assertEqual([s["scenario"] for s in report["scenarios"]], list(bdd.RUNTIME_BINDINGS))
        self.assertTrue(all(s["outcome"] == "BLOCKED" for s in report["scenarios"]))

    def test_changed_name_step_or_tag_fails_closed(self):
        text = (ROOT / "tests/features/runtime.feature").read_text()
        name = next(iter(bdd.RUNTIME_BINDINGS))
        for changed in (text.replace(name, name + " renamed"), text.replace("@AC-002", "@AC-003"),
                        text.replace("Given matching installed", "Given some installed")):
            with self.assertRaises(ValueError):
                bdd.runtime_report(changed)

    def test_catalog_capability_and_feature_data_are_consistent(self):
        report = automation_drift.validate(ROOT)
        self.assertEqual(report["errors"], [])
        self.assertTrue(report["valid"])


if __name__ == "__main__":
    unittest.main()
