"""AV-T029 integrity: the 002 graph is checked exactly, docs and CI stay honest. Offline only."""
import contextlib
import dataclasses
import io
import json
import os
from pathlib import Path
import re
import shutil
import tempfile
import unittest
from unittest import mock

from tools.package.inventory_sources import BANNED
from tools.testing import automation, discovery, drivers
from tools.validate import automation_drift, bdd

ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = ROOT / ".github/workflows/static.yml"
JOB = "automation-offline"
# The 002 offline unit-test modules the CI lane must run (the brief's list) plus this file.
REQUIRED_MODULES = ("test_bdd_bindings", "test_automation", "test_automation_runner",
                    "test_artifact_store", "test_coverage_report", "test_s002_integrity")
# Anything that fetches content or carries a credential must never appear in the public workflow.
FORBIDDEN_WORKFLOW = re.compile(
    r"curl|wget|invoke-webrequest|steamcmd|download-artifact|gh\s+release|pip\s+install|npm\s+(?:i|install)|"
    r"secrets\.|pull_request_target|biprivatekey|bikey|steam_|password|token|credential|--trust|"
    r"compile_gate|checkstart|diag_session|wb_compile|friendcycle|automation\s+run|automation\s+lane|--machine",
    re.I)
DRIVER_TOKEN = re.compile(r"\b(?:offline|native|deferred)\.[a-z_]+\b")
DOC_FILES = ("docs/tools/AUTOMATION.md", "README.md", "docs/MODULE_STATUS.md")


def read(relative):
    return (ROOT / relative).read_text(encoding="utf-8")


def unregistered_driver_claims(text, registry=None):
    """Driver-id-like tokens a document names that the registry (or the deferred marker) lacks."""
    known = set(drivers.DRIVERS if registry is None else registry) | {automation.DEFERRED_DRIVER}
    return sorted(set(DRIVER_TOKEN.findall(text)) - known)


def job_block(text, name):
    lines, block, inside = text.splitlines(), [], False
    for line in lines:
        if re.fullmatch(r"  [A-Za-z0-9_-]+:\s*", line):
            inside = line.strip() == name + ":"
        if inside:
            block.append(line)
    return "\n".join(block)


class TempRoot:
    """A synthetic root that shares the real tools tree and copies the 002 data files."""

    def __init__(self, test):
        self.dir = tempfile.TemporaryDirectory(prefix="hc-synthetic-s002-")
        test.addCleanup(self.dir.cleanup)
        self.root = Path(self.dir.name)
        try:
            os.symlink(ROOT / "tools", self.root / "tools", target_is_directory=True)
        except (OSError, NotImplementedError):
            test.skipTest("symlinks unavailable")
        (self.root / "tests").mkdir()
        for name in ("catalog.json", "capabilities.json"):
            shutil.copy(ROOT / "tests" / name, self.root / "tests" / name)
        shutil.copytree(ROOT / "tests/features", self.root / "tests/features")

    def edit_catalog(self, change):
        path = self.root / "tests/catalog.json"
        data = json.loads(path.read_text(encoding="utf-8"))
        change(data)
        path.write_text(json.dumps(data), encoding="utf-8")

    def edit_feature(self, name, change):
        path = self.root / "tests/features" / name
        path.write_text(change(path.read_text(encoding="utf-8")), encoding="utf-8")


def runtime_catalogue_ids():
    """Catalogue IDs the runtime protocol bindings tag, in binding order."""
    found = []
    for tags, _, _ in bdd.RUNTIME_BINDINGS.values():
        for tag in tags:
            match = automation_drift.ID_TAG.fullmatch(tag)
            if match and not match.group(1).startswith("AC-") and match.group(1) not in found:
                found.append(match.group(1))
    return found


class GraphIntegrityTests(unittest.TestCase):
    def test_repository_graph_is_valid_and_labelled_002(self):
        report = automation_drift.validate(ROOT)
        self.assertEqual(report["errors"], [])
        self.assertTrue(report["valid"])
        self.assertEqual(report["graph"], automation_drift.GRAPH)

    def test_repository_bindings_all_name_an_existing_unit_test_file(self):
        self.assertEqual([], automation_drift.unexecutable_bindings(ROOT))

    def test_a_binding_naming_a_missing_test_file_is_an_error(self):
        name = next(iter(bdd.BINDINGS))
        steps = bdd.BINDINGS[name][0]
        ghost = "Ghost binding without a suite"
        with mock.patch.dict(bdd.BINDINGS, {ghost: (steps, "test_no_such_suite_file.py")}):
            report = automation_drift.validate(ROOT)
        self.assertEqual([ghost], report["unexecutable_bindings"])
        self.assertFalse(report["valid"])
        self.assertTrue(any(ghost in error for error in report["errors"]))

    def test_001_validator_reports_002_graph_as_not_checked(self):
        stdout = io.StringIO()
        with mock.patch("sys.argv", ["bdd", "--runtime"]), contextlib.redirect_stdout(stdout):
            self.assertEqual(bdd.main(), 0)
        report = json.loads(stdout.getvalue())
        self.assertEqual(report["graph_002"], bdd.GRAPH_002_STATUS)
        self.assertNotEqual(report["graph_002"], "valid")
        self.assertNotIn("valid", report)
        module = report["graph_002_validator"]
        self.assertEqual(module, automation_drift.__name__)
        self.assertTrue((ROOT / (module.replace(".", "/") + ".py")).is_file())

    def test_001_validator_failure_also_denies_002_claim(self):
        stdout = io.StringIO()
        temp = TempRoot(self)
        broken = temp.root / "tests/features/other.feature"  # not the runtime protocol: must fail closed
        broken.write_text(read("tests/features/offline.feature"), encoding="utf-8")
        with mock.patch("sys.argv", ["bdd", "--runtime", str(broken)]), contextlib.redirect_stdout(stdout):
            self.assertEqual(bdd.main(), 1)
        report = json.loads(stdout.getvalue())
        self.assertIs(report["intact"], False)
        self.assertEqual(report["graph_002"], bdd.GRAPH_002_STATUS)

    def test_unknown_feature_tag_passes_001_but_fails_002(self):
        temp = TempRoot(self)
        unknown = "@CE-" + "9" * 3
        rows = {row["id"] for row in json.loads(read("tests/catalog.json"))["tests"]}
        self.assertNotIn(unknown[1:], rows)
        temp.edit_feature("offline.feature", lambda text: text.replace("  Scenario:", f"  {unknown}\n  Scenario:", 1))
        edited = (temp.root / "tests/features/offline.feature").read_text(encoding="utf-8")
        self.assertTrue(bdd.parse_scenarios(edited))  # the 001 parser admits it
        report = automation_drift.validate(temp.root)
        self.assertFalse(report["valid"])
        self.assertTrue(any(unknown in error for error in report["errors"]))

    def test_missing_catalogue_id_named_by_a_binding_fails_002_but_not_001(self):
        temp = TempRoot(self)
        victim = runtime_catalogue_ids()[0]
        temp.edit_catalog(lambda data: data.__setitem__(
            "tests", [row for row in data["tests"] if row["id"] != victim]))
        runtime = (temp.root / "tests/features/runtime.feature").read_text(encoding="utf-8")
        self.assertTrue(bdd.runtime_report(runtime)["scenarios"])  # the 001 runtime check stays intact
        report = automation_drift.validate(temp.root)
        self.assertFalse(report["valid"])
        self.assertTrue(any(victim in error for error in report["errors"]))

    def test_unknown_related_id_is_an_error(self):
        temp = TempRoot(self)
        ghost = "ZZ-001"
        temp.edit_catalog(lambda data: data["tests"][0]["related_ids"].append(ghost))
        report = automation_drift.validate(temp.root)
        self.assertFalse(report["valid"])
        self.assertTrue(any(ghost in error for error in report["errors"]))

    def test_changed_scenario_steps_and_missing_scenarios_are_errors(self):
        temp = TempRoot(self)
        first = next(iter(bdd.BINDINGS))
        step = bdd.BINDINGS[first][0][0]
        temp.edit_feature("offline.feature", lambda text: text.replace(step, step + " changed", 1))
        report = automation_drift.validate(temp.root)
        self.assertTrue(any(first in error for error in report["errors"]))
        temp.edit_feature("offline.feature", lambda text: text.replace("Scenario: " + first, "Scenario: " + first + " renamed", 1))
        report = automation_drift.validate(temp.root)
        self.assertTrue(any("no offline.feature scenario" in error and first in error for error in report["errors"]))

    def test_runtime_binding_with_a_malformed_task_is_an_error(self):
        name = next(iter(bdd.RUNTIME_BINDINGS))
        tags, steps, tasks = bdd.RUNTIME_BINDINGS[name]
        with mock.patch.dict(bdd.RUNTIME_BINDINGS, {name: (tags, steps, tasks + ("AV-T",))}):
            report = automation_drift.validate(ROOT)
        self.assertFalse(report["valid"])
        self.assertTrue(any("AV-T" in error and name in error for error in report["errors"]))

    def test_driver_registry_must_agree_with_the_catalogue_and_constants(self):
        first_id = sorted(drivers.DRIVERS)[0]
        driver = drivers.DRIVERS[first_id]
        unknown = "capability_that_no_row_requires"
        registry = dict(drivers.DRIVERS)
        registry[first_id] = dataclasses.replace(driver, needs=driver.needs + (unknown,))
        report = automation_drift.validate(ROOT, registry=registry)
        self.assertTrue(any(unknown in error for error in report["errors"]))
        registry = dict(drivers.DRIVERS)
        registry["offline.renamed"] = driver  # key differs from the driver's own ID
        self.assertFalse(automation_drift.validate(ROOT, registry=registry)["valid"])
        registry = dict(drivers.DRIVERS)
        registry[automation.DEFERRED_DRIVER] = driver
        self.assertFalse(automation_drift.validate(ROOT, registry=registry)["valid"])

    def test_every_driver_need_is_a_catalogue_capability(self):
        names = {name for row in json.loads(read("tests/catalog.json"))["tests"] for name in row["requires"]}
        for driver in drivers.DRIVERS.values():
            self.assertLessEqual(set(driver.needs), names, driver.id)


class DocsTests(unittest.TestCase):
    def test_docs_name_only_registered_drivers(self):
        for relative in DOC_FILES:
            self.assertEqual(unregistered_driver_claims(read(relative)), [], relative)

    def test_the_claim_check_flags_an_unregistered_adapter(self):
        invented = "native.never_registered"
        self.assertNotIn(invented, drivers.DRIVERS)
        self.assertEqual(unregistered_driver_claims(f"Works today: `{invented}`."), [invented])

    def test_native_drivers_are_not_documented_as_unrestricted(self):
        text = read("docs/tools/AUTOMATION.md")
        self.assertTrue(any(d.kind == "native" for d in drivers.DRIVERS.values()))
        self.assertIn("--trust", text)
        for task, _ in automation.DEFERRED_TASKS.items():
            self.assertIn(task, text)
        self.assertIn(automation.DEFERRED_REASON, text)

    def test_docs_name_no_banned_pack_text(self):
        compact = "".join(c for c in read("docs/tools/AUTOMATION.md").lower() if c.isalnum())
        self.assertFalse(any(word in compact for word in BANNED))

    def test_docs_do_not_quote_the_local_spec_tree(self):
        for relative in DOC_FILES[:1]:
            self.assertNotIn("docs/specs/", read(relative))

    def test_the_lane_command_and_module_documented_exist(self):
        text = read("docs/tools/AUTOMATION.md")
        for module in re.findall(r"-m (tools(?:\.[a-z_]+)+)", text):
            self.assertTrue((ROOT / (module.replace(".", "/") + ".py")).is_file(), module)
        self.assertIn("automation lane", text)
        self.assertTrue(callable(automation.lane_main))


class WorkflowTests(unittest.TestCase):
    def setUp(self):
        self.text = WORKFLOW.read_text(encoding="utf-8")
        self.block = job_block(self.text, JOB)

    def test_the_offline_job_exists_and_runs_on_pull_request(self):
        self.assertTrue(self.block, "job missing")
        self.assertRegex(self.text, r"(?m)^  pull_request:\s*$")
        self.assertNotRegex(self.block, r"(?m)^\s+if:")  # unconditional: no secret-dependent gating
        self.assertNotRegex(self.block, r"(?m)^\s+(?:environment|env):")

    def test_no_download_secret_credential_or_native_step(self):
        for line in self.text.splitlines():
            if line.lstrip().startswith("#"):
                continue
            self.assertIsNone(FORBIDDEN_WORKFLOW.search(line), line)
        self.assertRegex(self.text, r"(?m)^permissions:\n  contents: read\n")

    def test_only_checkout_and_setup_python_actions_are_used(self):
        actions = re.findall(r"uses:\s*(\S+)", self.text)
        self.assertTrue(actions)
        for action in actions:
            self.assertRegex(action, r"actions/(?:checkout|setup-python)@v\d+\Z")

    def test_the_job_runs_the_graph_check_and_the_framework_tests(self):
        self.assertIn("-m " + automation_drift.__name__, self.block)
        for module in REQUIRED_MODULES:
            self.assertIn("tests.unit." + module, self.block)
            self.assertTrue((ROOT / "tests/unit" / (module + ".py")).is_file(), module)
        for module in re.findall(r"-m (tools(?:\.[a-z_]+)+)", self.block):
            self.assertTrue((ROOT / (module.replace(".", "/") + ".py")).is_file(), module)


class LaneTests(unittest.TestCase):
    def setUp(self):
        patcher = mock.patch.dict(os.environ)
        patcher.start()
        self.addCleanup(patcher.stop)
        for name in ("GITHUB_ACTIONS", "CI"):
            os.environ.pop(name, None)
        self.natives = {key: d for key, d in drivers.DRIVERS.items() if d.kind == "native"}

    def capabilities(self, status):
        return {name: status for driver in self.natives.values() for name in driver.needs}

    def test_the_lane_never_reports_pass_even_with_every_capability_available(self):
        report = automation.native_lane(self.capabilities("available"))
        outcomes = {row["outcome"] for row in report["drivers"]}
        self.assertLessEqual(outcomes, {"BLOCKED", "NOTRUN"})
        self.assertIn(report["status"], ("BLOCKED", "NOTRUN"))
        self.assertEqual({row["id"] for row in report["drivers"] if row["kind"] == "driver"}, set(self.natives))

    def test_missing_capability_blocks_through_discovery(self):
        discovered = discovery.planner_capabilities(discovery.inventory(ROOT))
        report = automation.native_lane(discovered)
        for row in report["drivers"]:
            if row["kind"] == "driver":
                self.assertIn(row["outcome"], ("BLOCKED", "NOTRUN"))
                if any(discovered.get(name) != "available" for name in row["needs"]):
                    self.assertEqual(row["outcome"], "BLOCKED")
        self.assertEqual(automation.native_lane({})["status"], "BLOCKED")

    def test_deferred_tasks_stay_notrun_with_the_owner_reason(self):
        report = automation.native_lane(self.capabilities("available"))
        deferred = {row["id"]: row for row in report["drivers"] if row["kind"] == "deferred_task"}
        self.assertEqual(set(deferred), set(automation.DEFERRED_TASKS))
        for row in deferred.values():
            self.assertEqual((row["outcome"], row["reason"]), ("NOTRUN", automation.DEFERRED_REASON))

    def test_a_driver_with_no_needs_is_notrun_never_pass(self):
        driver = dataclasses.replace(next(iter(self.natives.values())), id="native.synthetic", needs=())
        report = automation.native_lane({}, registry={driver.id: driver})
        row = next(row for row in report["drivers"] if row["id"] == driver.id)
        self.assertEqual(row["outcome"], "NOTRUN")

    def test_hosted_ci_is_refused(self):
        for name in ("GITHUB_ACTIONS", "CI"):
            report = automation.native_lane(self.capabilities("available"), environ={name: "true"})
            self.assertTrue(report["hosted_ci"])
            self.assertTrue(all(row["outcome"] != "PASS" for row in report["drivers"]))
            self.assertTrue(all(row["reason"] == "hosted_ci_refused" for row in report["drivers"] if row["kind"] == "driver"))
        stdout = io.StringIO()
        with mock.patch.dict(os.environ, {"GITHUB_ACTIONS": "true"}), contextlib.redirect_stdout(stdout):
            self.assertEqual(automation.lane_main([]), 1)

    def test_run_with_trust_is_refused_in_hosted_ci_like_the_lane(self):
        for name in ("GITHUB_ACTIONS", "CI"):
            with self.subTest(name=name), tempfile.TemporaryDirectory() as directory:
                output = Path(directory) / "run"
                stdout = io.StringIO()
                with mock.patch.dict(os.environ, {name: "true"}), contextlib.redirect_stdout(stdout), \
                        mock.patch.object(automation, "run_automation") as runner:
                    code = automation.run_main(["manifest.json", str(output), "--trust", "native.synthetic"])
                self.assertEqual(code, 1)
                runner.assert_not_called()
                self.assertFalse(output.exists())
                report = json.loads(stdout.getvalue())
                self.assertEqual((report["refused"], report["reason"], report["hosted_ci"]),
                                 (True, "hosted_ci_refused", True))

    def test_run_without_trust_is_not_refused_in_hosted_ci(self):
        done = {"run_id": "r", "status": "PASS", "complete": True, "counts": {}, "task_counts": {}}
        with tempfile.TemporaryDirectory() as directory:
            manifest = Path(directory) / "manifest.json"
            manifest.write_text("{}", encoding="utf-8")
            with mock.patch.dict(os.environ, {"GITHUB_ACTIONS": "true"}), contextlib.redirect_stdout(io.StringIO()), \
                    mock.patch.object(automation, "run_automation", return_value=done) as runner:
                code = automation.run_main([str(manifest), str(Path(directory) / "run")])
        self.assertEqual(code, 0)
        runner.assert_called_once()
        self.assertEqual(list(runner.call_args.kwargs["trusted_drivers"]), [])

    def test_lane_cli_prints_one_json_report_and_states_the_rules(self):
        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            self.assertEqual(automation.main(["lane"]), 0)
        report = json.loads(stdout.getvalue())
        self.assertEqual(report["lane"], "local-native")
        self.assertEqual(report["rules"], list(automation.LANE_RULES))
        self.assertTrue(report["unimplemented"])
        self.assertNotIn("PASS", {row["outcome"] for row in report["drivers"]})


if __name__ == "__main__":
    unittest.main()
