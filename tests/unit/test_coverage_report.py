"""Coverage, human-review and blocker report tests (spec 002 AV-T027).

Synthetic: they never establish DayZ behaviour. Expectations derive from the catalogue, the
capability table, the outcome constants and the driver registry; no counts are pinned.
"""
import contextlib
import copy
import io
import json
from pathlib import Path
import tempfile
import unittest

from tools.testing import artifacts, automation, coverage, discovery, drivers
from tools.validate import evidence

ROOT = Path(__file__).resolve().parents[2]
CATALOG = automation.load_catalog(ROOT / "tests/catalog.json")
IDS = [row["id"] for row in CATALOG["tests"]]
ALL_AVAILABLE = {name: "available" for name in discovery.capability_names(ROOT)}
DRIVER = drivers.Driver("t.offline", "offline", "synthetic", (), lambda root, inputs: ["x"], drivers.judge_exit)
PINS = artifacts.pins_for({DRIVER.id: DRIVER})
METHOD = "synthetic layer=offline-framework clients=0 (never multiplayer)"


def make_store(root, attempts, run_id="synthetic"):
    """Seal one attempt per (task, outcome) pair, in order; repeated tasks form a chain."""
    store = artifacts.ArtifactStore(Path(root) / "evidence", run_id)
    for task, outcome in attempts:
        attempt = store.begin(task, DRIVER.id, actor="offline", presented_as="offline_framework",
                              client_count=0, pin=PINS[DRIVER.id])
        attempt.add("driver.log", f"{task} {outcome}\n", "driver_log")
        automation._record(attempt, task, outcome, "synthetic", METHOD, ["read the log", "rerun"])
        attempt.finish(outcome, "synthetic")
    return store


def narrowed(modes, requires=()):
    """Catalogue copy whose first row has the given modes and requirements; every id is unchanged."""
    catalog = copy.deepcopy(CATALOG)
    catalog["tests"][0]["modes"] = list(modes)
    catalog["tests"][0]["requires"] = list(requires)
    return catalog


class CoverageCase(unittest.TestCase):
    def setUp(self):
        scratch = tempfile.TemporaryDirectory()
        self.addCleanup(scratch.cleanup)
        self.dir = Path(scratch.name)

    def build(self, store, catalog=CATALOG, covers=None, **kwargs):
        kwargs.setdefault("capabilities", ALL_AVAILABLE)
        return coverage.build_report(catalog, store.root, run_id="synthetic", covers=covers or {}, pins=PINS,
                                     manifest_sha256=store.manifest_sha256(), **kwargs)

    def item(self, report, identifier):
        return next(item for item in report["items"] if item["id"] == identifier)


class ListingTests(CoverageCase):
    def test_every_catalogue_id_is_reported_not_only_runnable_ones(self):
        report = self.build(make_store(self.dir, []))
        self.assertEqual([item["id"] for item in report["items"]], IDS)
        self.assertTrue(set(automation.ORIGINAL_IDS) <= {item["id"] for item in report["items"]})
        self.assertEqual(sum(report["counts"].values()), len(IDS))
        self.assertEqual(set(report["counts"]), set(coverage.OUTCOMES))
        for item in report["items"]:
            self.assertIn(item["outcome"], coverage.OUTCOMES)
            self.assertEqual([s["mode"] for s in item["submethods"]],
                             next(r["modes"] for r in CATALOG["tests"] if r["id"] == item["id"]))

    def test_reconciliation_is_exact_and_traces_each_criterion(self):
        report = self.build(make_store(self.dir, []))
        self.assertEqual(report["reconciliation"]["errors"], [])
        self.assertEqual(report["reconciliation"]["catalogue_count"], report["reconciliation"]["reported_count"])
        for row, item in zip(CATALOG["tests"], report["items"]):
            self.assertEqual(item["trace"]["criterion"], row["criterion"])
            self.assertTrue(item["trace"]["sources"])
            self.assertEqual(item["trace"]["related_ids"], row["related_ids"])

    def test_missing_extra_and_miscounted_ids_are_errors(self):
        report = self.build(make_store(self.dir, []))
        items = report["items"]
        codes = lambda found: {(e["code"], e.get("id")) for e in found["errors"]}
        short = coverage.reconcile(CATALOG, items[1:], {}, {})
        self.assertIn(("missing_from_report", IDS[0]), codes(short))
        self.assertIn("count_mismatch", {e["code"] for e in short["errors"]})
        extra = copy.deepcopy(items[0], memo={})
        extra["id"] = "ZZZ-999"
        self.assertIn(("extra_in_report", "ZZZ-999"), codes(coverage.reconcile(CATALOG, items + [extra], {}, {})))
        dropped = copy.deepcopy(CATALOG)
        original = next(i for i, row in enumerate(dropped["tests"]) if row["origin"] == "original")
        gone = dropped["tests"].pop(original)["id"]
        found = self.build(make_store(self.dir / "b", []), catalog=dropped)
        self.assertIn(("missing_original", gone), codes(found["reconciliation"]))
        self.assertFalse(found["complete"])
        self.assertNotEqual(found["status"], "PASS")

    def test_unknown_covered_id_and_missing_covering_task_are_errors(self):
        report = self.build(make_store(self.dir, [("T-1", "PASS")]),
                            covers={"T-1": ["ZZZ-999"], "T-missing": [IDS[0]]})
        found = {(e["code"]) for e in report["reconciliation"]["errors"]}
        self.assertTrue({"covers_unknown_id", "covering_task_missing"} <= found)


class AcceptanceTests(CoverageCase):
    def test_acceptance_is_never_promoted_and_review_defaults_to_not_reviewed(self):
        report = self.build(make_store(self.dir, [("T-1", "PASS")]), covers={"T-1": IDS})
        self.assertEqual((report["acceptance"], report["multiplayer"]), ("not_evaluated", "never_proven"))
        for item in report["items"]:
            self.assertEqual(item["acceptance"]["state"], coverage.ACCEPTANCE_STATE)
            self.assertEqual(item["human_review"], {"state": coverage.NOT_REVIEWED})
            self.assertFalse(item["evidence_class"]["accepted"])
            self.assertNotEqual(item["outcome"], "PASS")

    def test_unqualified_pass_supports_but_never_passes_a_submethod(self):
        row = CATALOG["tests"][0]
        report = self.build(make_store(self.dir, [("T-1", "PASS")]), catalog=narrowed(["measurement", "engine"]),
                            covers={"T-1": [row["id"]]})
        item = self.item(report, row["id"])
        self.assertEqual(item["evidence_class"]["synthetic_supporting"], ["T-1"])
        self.assertEqual([s["outcome"] for s in item["submethods"]], ["BLOCKED", "BLOCKED"])
        self.assertEqual(item["outcome"], "BLOCKED")

    def test_a_qualified_submethod_cannot_hide_an_unqualified_one(self):
        row = CATALOG["tests"][0]
        store = make_store(self.dir, [("T-1", "PASS")])
        covers = {"T-1": [row["id"]]}
        qualified = {DRIVER.id: {"measurement"}}
        both = self.item(self.build(store, catalog=narrowed(["measurement", "engine"]), covers=covers,
                                    qualified=qualified), row["id"])
        results = {s["mode"]: s["outcome"] for s in both["submethods"]}
        self.assertEqual(results, {"measurement": "PASS", "engine": "BLOCKED"})
        self.assertEqual(both["outcome"], "BLOCKED")
        self.assertIn("unsupported_submethod:engine", both["reason"])
        only = self.item(self.build(store, catalog=narrowed(["measurement"]), covers=covers, qualified=qualified),
                         row["id"])
        self.assertEqual(only["outcome"], "PASS")
        self.assertEqual(only["acceptance"]["state"], coverage.ACCEPTANCE_STATE)

    def test_human_judgment_and_client_pair_are_never_passed_by_a_driver(self):
        row = CATALOG["tests"][0]
        store = make_store(self.dir, [("T-1", "PASS")])
        every = {DRIVER.id: set(coverage.MODES)}
        report = self.build(store, catalog=narrowed(["human-judgment", "client-pair"]),
                            covers={"T-1": [row["id"]]}, qualified=every)
        self.assertEqual([s["outcome"] for s in self.item(report, row["id"])["submethods"]], ["BLOCKED", "BLOCKED"])

    def test_deferred_capability_is_notrun_with_the_owner_reason(self):
        deferred = sorted(discovery.DEFERRED_CAPABILITIES)[0]
        capabilities = dict(ALL_AVAILABLE, **{deferred: "unverified"})
        row = next(row for row in CATALOG["tests"] if deferred in row["requires"])
        item = self.item(self.build(make_store(self.dir, []), capabilities=capabilities), row["id"])
        self.assertEqual((item["outcome"], item["reason"]), ("NOTRUN", automation.DEFERRED_REASON))
        self.assertTrue(item["next"])


class RetryTests(CoverageCase):
    def test_failed_retry_stays_visible_when_a_later_attempt_passes(self):
        row = CATALOG["tests"][0]
        report = self.build(make_store(self.dir, [("T-1", "FAIL"), ("T-1", "PASS")]),
                            catalog=narrowed(["measurement"]), covers={"T-1": [row["id"]]},
                            qualified={DRIVER.id: {"measurement"}})
        view = self.item(report, row["id"])["tasks"][0]
        self.assertEqual([a["outcome"] for a in view["attempts"]], ["FAIL", "PASS"])
        self.assertEqual(view["failed_attempts"], 1)
        self.assertTrue(view["passed_after_failure"])
        self.assertEqual(view["attempts"][1]["previous"], view["attempts"][0]["entry_sha256"])
        self.assertIn("T-1", coverage.markdown(report))

    def test_a_failing_latest_attempt_fails_the_row_even_after_an_earlier_pass(self):
        row = CATALOG["tests"][0]
        report = self.build(make_store(self.dir, [("T-1", "PASS"), ("T-1", "FAIL")]), covers={"T-1": [row["id"]]})
        item = self.item(report, row["id"])
        self.assertEqual((item["outcome"], item["reason"]), ("FAIL", "covering_task_failed"))
        self.assertEqual(report["status"], "FAIL")

    def test_framework_tasks_list_every_attempt(self):
        report = self.build(make_store(self.dir, [("T-1", "FAIL"), ("T-1", "FAIL"), ("T-2", "PASS")]))
        chains = {view["task"]: len(view["attempts"]) for view in report["framework_tasks"]}
        self.assertEqual(chains, {"T-1": 2, "T-2": 1})


class BlockerTests(CoverageCase):
    def test_every_catalogue_capability_has_a_next_step_and_every_blocked_item_names_one(self):
        needed = {name for row in CATALOG["tests"] for name in row["requires"]}
        self.assertEqual(needed - set(coverage.CAPABILITY_NEXT), set())
        for mode, kind_step in coverage.MODE_NEXT.items():
            self.assertIn(kind_step[0], coverage.BLOCKER_KINDS)
        report = self.build(make_store(self.dir, []), capabilities={})
        blocked = [item for item in report["items"] if item["outcome"] == "BLOCKED"]
        self.assertTrue(blocked)
        for item in blocked:
            self.assertTrue(item["next"])
            self.assertTrue(set(item["blocker_kinds"]) <= set(coverage.BLOCKER_KINDS))
            for sub in item["submethods"]:
                if sub["outcome"] == "BLOCKED":
                    self.assertTrue(sub["next"])
                    self.assertIn(sub["blocker_kind"], coverage.BLOCKER_KINDS)
        self.assertTrue(report["next_steps"])

    def test_unmapped_capability_still_gets_a_concrete_next_step(self):
        catalog = narrowed(["measurement"], ["synthetic_unmapped_capability"])
        item = self.item(self.build(make_store(self.dir, []), catalog=catalog, capabilities={}), IDS[0])
        self.assertEqual(item["outcome"], "BLOCKED")
        self.assertIn("synthetic_unmapped_capability", " ".join(item["next"]))

    def test_unselected_rows_are_notrun(self):
        report = self.build(make_store(self.dir, []), selected=[IDS[0]])
        self.assertEqual({i["reason"] for i in report["items"] if i["id"] != IDS[0]}, {"not_selected"})


class HumanReviewTests(CoverageCase):
    def review(self, store, **changes):
        entry = json.loads((store.root / evidence.STORE_MANIFEST).read_text())["attempts"][0]
        cited = entry["artifacts"][0]
        value = {"decision": "yes", "reviewer": "synthetic reviewer",
                 "artifact": {"path": cited["path"], "sha256": cited["sha256"]}}
        value.update(changes)
        return value

    def test_a_decision_counts_only_when_it_cites_a_sealed_artifact(self):
        row = CATALOG["tests"][0]
        store = make_store(self.dir, [("T-1", "PASS")])
        catalog = narrowed(["human-judgment"])
        good = self.item(self.build(store, catalog=catalog, reviews={row["id"]: self.review(store)}), row["id"])
        self.assertEqual(good["human_review"]["state"], "reviewed_yes")
        self.assertEqual(good["outcome"], "PASS")
        self.assertEqual(good["acceptance"]["state"], coverage.ACCEPTANCE_STATE)
        bad = {"wrong hash": {"artifact": {"path": self.review(store)["artifact"]["path"], "sha256": "0" * 64}},
               "no artifact": {"artifact": None}, "no reviewer": {"reviewer": ""},
               "bad decision": {"decision": "maybe"}}
        for label, change in bad.items():
            report = self.build(store, catalog=catalog, reviews={row["id"]: self.review(store, **change)})
            item = self.item(report, row["id"])
            self.assertEqual(item["human_review"], {"state": coverage.NOT_REVIEWED}, label)
            self.assertEqual(item["outcome"], "BLOCKED", label)
            self.assertIn(row["id"], report["human_review"]["rejected"], label)

    def test_a_no_decision_fails_the_row(self):
        row = CATALOG["tests"][0]
        store = make_store(self.dir, [("T-1", "PASS")])
        item = self.item(self.build(store, catalog=narrowed(["human-judgment"]),
                                    reviews={row["id"]: self.review(store, decision="no")}), row["id"])
        self.assertEqual((item["outcome"], item["human_review"]["state"]), ("FAIL", "reviewed_no"))


class StoreIntegrityTests(CoverageCase):
    def test_a_tampered_store_is_incomplete_and_supports_nothing(self):
        row = CATALOG["tests"][0]
        store = make_store(self.dir, [("T-1", "PASS")])
        kwargs = dict(catalog=narrowed(["measurement"]), covers={"T-1": [row["id"]]},
                      qualified={DRIVER.id: {"measurement"}})
        self.assertEqual(self.item(self.build(store, **kwargs), row["id"])["outcome"], "PASS")
        log = next(store.root.rglob("driver.log"))
        log.chmod(0o644)
        log.write_text("replaced\n")
        report = self.build(store, **kwargs)
        self.assertEqual(report["status"], "INCOMPLETE")
        self.assertFalse(report["store"]["valid"])
        self.assertTrue(report["store"]["errors"])
        self.assertNotEqual(self.item(report, row["id"])["outcome"], "PASS")
        self.assertEqual(report["counts"]["PASS"], 0)

    def test_a_missing_store_manifest_is_incomplete(self):
        empty = self.dir / "evidence"
        empty.mkdir()
        report = coverage.build_report(CATALOG, empty, run_id="synthetic", pins=PINS, capabilities=ALL_AVAILABLE)
        self.assertEqual((report["status"], report["complete"]), ("INCOMPLETE", False))


class OutputTests(CoverageCase):
    def test_outputs_are_json_plus_short_markdown_in_the_out_dir_only(self):
        report = self.build(make_store(self.dir, [("T-1", "FAIL")]))
        written = coverage.write_outputs(self.dir / "out", report)
        data = json.loads((self.dir / "out" / written["json"]).read_text())
        self.assertEqual(data["counts"], report["counts"])
        text = (self.dir / "out" / written["markdown"]).read_text()
        self.assertLess(len(text.splitlines()), 120)
        for name in coverage.OUTCOMES:
            self.assertIn(name, text)
        self.assertNotIn(str(Path.home()), text + json.dumps(data))
        with self.assertRaises(ValueError):
            coverage.write_outputs(self.dir / "out", report)

    def test_the_repository_is_refused(self):
        report = self.build(make_store(self.dir, []))
        with self.assertRaises(ValueError):
            coverage.write_outputs(ROOT / "coverage-must-not-exist", report)
        self.assertFalse((ROOT / "coverage-must-not-exist").exists())


class RunnerIntegrationTests(CoverageCase):
    manifest = {"schema_version": 1, "run_id": "synthetic", "tasks": []}

    def test_run_writes_coverage_and_the_subcommand_rebuilds_it_from_the_sealed_store(self):
        run_dir = self.dir / "run"
        report = automation.run_automation(self.manifest, run_dir, capabilities=ALL_AVAILABLE)
        written = report["coverage_report"]
        self.assertTrue(written["written"])
        first = json.loads((run_dir / written["json"]).read_text())
        self.assertEqual(first["reconciliation"]["errors"], [])
        self.assertEqual(sum(first["counts"].values()), len(IDS))
        self.assertEqual({v["task"] for v in first["framework_tasks"]}, set(automation.DEFERRED_TASKS))
        manifest_path = self.dir / "manifest.json"
        manifest_path.write_text(json.dumps(self.manifest))
        with contextlib.redirect_stdout(io.StringIO()):
            code = automation.main(["coverage", str(run_dir), str(manifest_path), "--out", str(self.dir / "again")])
        self.assertEqual(code, 0 if first["status"] not in ("FAIL", "INCOMPLETE") else 1)
        again = json.loads((self.dir / "again" / "coverage.json").read_text())
        self.assertEqual(again["counts"], first["counts"])
        self.assertEqual(again["status"], first["status"])

    def test_a_manifest_for_another_run_is_refused(self):
        run_dir = self.dir / "run"
        automation.run_automation(self.manifest, run_dir, capabilities=ALL_AVAILABLE)
        other = self.dir / "other.json"
        other.write_text(json.dumps(dict(self.manifest, run_id="different")))
        with self.assertRaises(SystemExit), contextlib.redirect_stderr(io.StringIO()):
            automation.main(["coverage", str(run_dir), str(other), "--out", str(self.dir / "x")])

    def test_coverage_files_do_not_break_the_sealed_store(self):
        run_dir = self.dir / "run"
        automation.run_automation(self.manifest, run_dir, capabilities=ALL_AVAILABLE)
        self.assertTrue((run_dir / "coverage.json").is_file())
        result = evidence.validate_store(run_dir / "evidence", pins=coverage.pins_for_run(drivers.DRIVERS))
        self.assertTrue(result["valid"], result["errors"])


if __name__ == "__main__":
    unittest.main()
